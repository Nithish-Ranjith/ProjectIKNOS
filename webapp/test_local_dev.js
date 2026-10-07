import puppeteer from 'puppeteer';

(async () => {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.text().toLowerCase().includes('mapbox') || msg.text().toLowerCase().includes('canvas')) {
      console.log(`PAGE LOG [${msg.type()}]:`, msg.text());
    }
  });
  
  page.on('pageerror', error => {
    console.log('PAGE ERROR:', error.message);
  });

  const baseUrl = 'http://localhost:5177';
  console.log(`Navigating to ${baseUrl} to inject session...`);
  
  // Go to root just to set localStorage on the right origin
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  
  await page.evaluate(() => {
    localStorage.setItem('demo_session', JSON.stringify({
      role: 'surveyor',
      email: 'surveyor@iknos.app'
    }));
  });

  const missionUrl = `${baseUrl}/surveyor/mission/C01/parcel`;
  console.log(`Navigating to ${missionUrl}...`);
  
  try {
    const response = await page.goto(missionUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    console.log(`Navigation response: ${response?.status()} ${response?.statusText()}`);
  } catch (err) {
    console.log('Navigation Error:', err);
  }

  // Wait 10 seconds to let the map initialize and load tiles
  console.log('Waiting 10 seconds for Mapbox to initialize...');
  await new Promise(r => setTimeout(r, 10000));
  
  // Scrape dimensions of the Mapbox canvas
  const canvasSize = await page.evaluate(() => {
    const canvas = document.querySelector('.mapboxgl-canvas');
    if (!canvas) return 'NO CANVAS FOUND';
    const rect = canvas.getBoundingClientRect();
    return `${rect.width}x${rect.height}`;
  });
  
  console.log('Mapbox Canvas Render Size:', canvasSize);
  
  // Scrape the DOM for any error messages
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 500));
  console.log('Body Text Snippet:', bodyText);

  await page.screenshot({ path: '/Users/nithishranjith/.gemini/antigravity-ide/brain/01bad735-f95e-460f-a7a6-222c014cc4a4/scratch/local_map.png', fullPage: true });

  await browser.close();
  console.log('Done.');
})();
