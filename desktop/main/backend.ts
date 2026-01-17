import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';
import { app } from 'electron';

export type BackendStatus = 'starting' | 'running' | 'stopped' | 'error';

export class BackendManager {
  private process: ChildProcess | null = null;
  private status: BackendStatus = 'stopped';
  private isDev: boolean;
  private restartAttempts = 0;
  private maxRestartAttempts = 3;
  private healthCheckInterval: NodeJS.Timeout | null = null;

  constructor(isDev: boolean) {
    this.isDev = isDev;
  }

  getStatus(): BackendStatus {
    return this.status;
  }

  private getBackendPath(): string {
    if (this.isDev) {
      // In development, run the Python backend directly
      return path.join(__dirname, '..', '..', 'backend');
    } else {
      // In production, use the bundled executable
      const resourcesPath = process.resourcesPath;
      const exeName = process.platform === 'win32' ? 'pool-telemetry-backend.exe' : 'pool-telemetry-backend';
      return path.join(resourcesPath, 'backend', exeName);
    }
  }

  async start(): Promise<void> {
    if (this.status === 'running' || this.status === 'starting') {
      console.log('Backend already running or starting');
      return;
    }

    this.status = 'starting';
    console.log('Starting backend...');

    try {
      if (this.isDev) {
        // In development, start Python directly
        await this.startDevelopmentBackend();
      } else {
        // In production, start the bundled executable
        await this.startProductionBackend();
      }

      // Start health checks
      this.startHealthCheck();
    } catch (error) {
      console.error('Failed to start backend:', error);
      this.status = 'error';
      throw error;
    }
  }

  private async startDevelopmentBackend(): Promise<void> {
    const backendPath = this.getBackendPath();
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    console.log(`Starting development backend at ${backendPath}`);

    this.process = spawn(pythonCmd, ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload'], {
      cwd: backendPath,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'
      },
      stdio: ['ignore', 'pipe', 'pipe']
    });

    this.setupProcessHandlers();
    await this.waitForBackend();
  }

  private async startProductionBackend(): Promise<void> {
    const backendPath = this.getBackendPath();
    console.log(`Starting production backend at ${backendPath}`);

    this.process = spawn(backendPath, [], {
      cwd: path.dirname(backendPath),
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'
      },
      stdio: ['ignore', 'pipe', 'pipe']
    });

    this.setupProcessHandlers();
    await this.waitForBackend();
  }

  private setupProcessHandlers(): void {
    if (!this.process) return;

    this.process.stdout?.on('data', (data: Buffer) => {
      console.log(`[Backend] ${data.toString().trim()}`);
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error(`[Backend Error] ${data.toString().trim()}`);
    });

    this.process.on('error', (error) => {
      console.error('Backend process error:', error);
      this.status = 'error';
    });

    this.process.on('exit', (code, signal) => {
      console.log(`Backend process exited with code ${code}, signal ${signal}`);
      this.process = null;

      if (this.status !== 'stopped') {
        this.status = 'error';
        this.handleUnexpectedExit();
      }
    });
  }

  private async handleUnexpectedExit(): Promise<void> {
    if (this.restartAttempts < this.maxRestartAttempts) {
      this.restartAttempts++;
      console.log(`Attempting to restart backend (attempt ${this.restartAttempts}/${this.maxRestartAttempts})`);

      // Wait a bit before restarting
      await new Promise(resolve => setTimeout(resolve, 2000));

      try {
        await this.start();
        this.restartAttempts = 0; // Reset on successful restart
      } catch (error) {
        console.error('Failed to restart backend:', error);
      }
    } else {
      console.error('Max restart attempts reached. Backend will not be restarted.');
    }
  }

  private async waitForBackend(maxWaitMs = 30000): Promise<void> {
    const startTime = Date.now();
    const checkInterval = 500;

    while (Date.now() - startTime < maxWaitMs) {
      const isHealthy = await this.checkHealth();
      if (isHealthy) {
        console.log('Backend is healthy');
        this.status = 'running';
        return;
      }
      await new Promise(resolve => setTimeout(resolve, checkInterval));
    }

    throw new Error('Backend failed to start within timeout');
  }

  private async checkHealth(): Promise<boolean> {
    return new Promise((resolve) => {
      const req = http.request(
        {
          hostname: 'localhost',
          port: 8000,
          path: '/api/health',
          method: 'GET',
          timeout: 2000
        },
        (res) => {
          resolve(res.statusCode === 200);
        }
      );

      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });

      req.end();
    });
  }

  private startHealthCheck(): void {
    // Check health every 30 seconds
    this.healthCheckInterval = setInterval(async () => {
      if (this.status === 'running') {
        const isHealthy = await this.checkHealth();
        if (!isHealthy) {
          console.warn('Backend health check failed');
          this.status = 'error';
          this.handleUnexpectedExit();
        }
      }
    }, 30000);
  }

  async stop(): Promise<void> {
    console.log('Stopping backend...');
    this.status = 'stopped';

    // Clear health check interval
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }

    if (this.process) {
      return new Promise((resolve) => {
        const killTimeout = setTimeout(() => {
          console.log('Force killing backend process');
          this.process?.kill('SIGKILL');
          resolve();
        }, 5000);

        this.process!.on('exit', () => {
          clearTimeout(killTimeout);
          resolve();
        });

        // Try graceful shutdown first
        if (process.platform === 'win32') {
          this.process!.kill();
        } else {
          this.process!.kill('SIGTERM');
        }
      });
    }
  }

  async restart(): Promise<void> {
    await this.stop();
    await new Promise(resolve => setTimeout(resolve, 1000));
    await this.start();
  }
}
