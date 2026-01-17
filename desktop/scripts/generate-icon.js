const sharp = require('sharp');
const fs = require('fs');
const path = require('path');
const pngToIco = require('png-to-ico');

const resourcesDir = path.join(__dirname, '..', 'resources');
const svgPath = path.join(resourcesDir, 'icon.svg');
const icoPath = path.join(resourcesDir, 'icon.ico');
const pngPath = path.join(resourcesDir, 'icon.png');

const sizes = [16, 32, 48, 64, 128, 256];

async function generateIcon() {
  console.log('Generating icons from SVG...');

  const svgBuffer = fs.readFileSync(svgPath);
  const pngBuffers = [];

  // Generate PNGs at different sizes
  for (const size of sizes) {
    const pngBuffer = await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toBuffer();
    pngBuffers.push(pngBuffer);
    console.log(`  Generated ${size}x${size} PNG`);
  }

  // Save 256x256 as main PNG
  await sharp(svgBuffer)
    .resize(256, 256)
    .png()
    .toFile(pngPath);
  console.log('  Saved icon.png (256x256)');

  // Convert to ICO
  const icoBuffer = await pngToIco(pngBuffers);
  fs.writeFileSync(icoPath, icoBuffer);
  console.log('  Saved icon.ico');

  console.log('Icon generation complete!');
}

generateIcon().catch(console.error);
