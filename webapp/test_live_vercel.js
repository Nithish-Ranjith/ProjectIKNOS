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

  const baseUrl = 'https://project-iknos-hhr22v4d7-nithish-ranjiths-projects.vercel.app';
  console.log(`Navigating to ${baseUrl} to inject session...`);
  
  // Go to root just to set localStorage on the right origin
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  
  await page.evaluate(() => {
    localStorage.setItem('demo_session', JSON.stringify({
      role: 'surveyor',
      email: 'surveyor@iknos.app'
    }));
  });

  const missionUrl = `${baseUrl}/cases/C01/mission`;
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
  
  // Scrape dimensions of the Mapbox canvas to prove it resized correctly!
  const canvasSize = await page.evaluate(() => {
    const canvas = document.querySelector('.mapboxgl-canvas');
    if (!canvas) return 'NO CANVAS FOUND';
    const rect = canvas.getBoundingClientRect();
    return `${rect.width}x${rect.height}`;
  });
  
  console.log('Mapbox Canvas Render Size:', canvasSize);

  await browser.close();
  console.log('Done.');
})();
