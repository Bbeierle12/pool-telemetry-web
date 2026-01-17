const esbuild = require('esbuild');
const path = require('path');

const isWatch = process.argv.includes('--watch');

async function build() {
  const ctx = await esbuild.context({
    entryPoints: [path.join(__dirname, '..', 'main', 'main.ts')],
    bundle: true,
    platform: 'node',
    target: 'node18',
    outfile: path.join(__dirname, '..', 'dist', 'main', 'main.js'),
    external: [
      'electron',  // Externalize electron - Electron provides this at runtime
      'electron-store',  // Keep as external since it has native dependencies
    ],
    sourcemap: true,
    format: 'cjs',
    // Also build preload
    plugins: [],
  });

  if (isWatch) {
    await ctx.watch();
    console.log('Watching for changes...');
  } else {
    await ctx.rebuild();
    await ctx.dispose();
    console.log('Build complete');
  }
}

// Build preload separately
async function buildPreload() {
  const ctx = await esbuild.context({
    entryPoints: [path.join(__dirname, '..', 'main', 'preload.ts')],
    bundle: true,
    platform: 'node',
    target: 'node18',
    outfile: path.join(__dirname, '..', 'dist', 'main', 'preload.js'),
    external: ['electron'],
    sourcemap: true,
    format: 'cjs',
  });

  if (isWatch) {
    await ctx.watch();
  } else {
    await ctx.rebuild();
    await ctx.dispose();
  }
}

// Build backend manager
async function buildBackend() {
  const ctx = await esbuild.context({
    entryPoints: [path.join(__dirname, '..', 'main', 'backend.ts')],
    bundle: true,
    platform: 'node',
    target: 'node18',
    outfile: path.join(__dirname, '..', 'dist', 'main', 'backend.js'),
    external: ['electron'],
    sourcemap: true,
    format: 'cjs',
  });

  if (isWatch) {
    await ctx.watch();
  } else {
    await ctx.rebuild();
    await ctx.dispose();
  }
}

Promise.all([build(), buildPreload(), buildBackend()])
  .then(() => {
    if (!isWatch) {
      console.log('All builds complete!');
    }
  })
  .catch((err) => {
    console.error('Build failed:', err);
    process.exit(1);
  });
