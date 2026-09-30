const puppeteer = require('puppeteer');

(async () => {
  console.log("Starting Puppeteer...");
  const browser = await puppeteer.launch({ headless: "new", args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.toString()));
  
  console.log("Navigating to http://localhost:5173/surveyor/cases ...");
  await page.goto('http://localhost:5173/surveyor/cases', { waitUntil: 'networkidle2' });
  
  console.log("Waiting for case list...");
  await page.waitForSelector('td'); // wait for cases
  
  console.log("Clicking the first mission...");
  const firstMission = await page.$('td');
  await firstMission.click();
  
  console.log("Waiting for Parcel Step...");
  await page.waitForSelector('button');
  
  // Wait a bit
  await new Promise(r => setTimeout(r, 2000));
  
  // Look for the "Proceed to Plan" button
  console.log("Clicking Proceed to Plan...");
  const buttons = await page.$$('button');
  let clicked = false;
  for (let b of buttons) {
      const text = await page.evaluate(el => el.textContent, b);
      if (text.includes("Proceed to Plan")) {
          await b.click();
          clicked = true;
          break;
      }
  }
  
  if (!clicked) {
      console.log("Could not find Proceed to Plan button. Clicking Approve Boundary if present...");
      for (let b of buttons) {
          const text = await page.evaluate(el => el.textContent, b);
          if (text.includes("Approve Boundary")) {
              await b.click();
              // wait for state change
              await new Promise(r => setTimeout(r, 1000));
              const btns2 = await page.$$('button');
              for (let b2 of btns2) {
                  const text2 = await page.evaluate(el => el.textContent, b2);
                  if (text2.includes("Proceed to Plan")) {
                      await b2.click();
                      clicked = true;
                      break;
                  }
              }
              break;
          }
      }
  }
  
  console.log("Waiting for Plan Step...");
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("Clicking Lock Plan...");
  const planButtons = await page.$$('button');
  for (let b of planButtons) {
      const text = await page.evaluate(el => el.textContent, b);
      if (text.includes("Lock Plan")) {
          await b.click();
          console.log("Clicked Lock Plan!");
          break;
      }
  }
  
  // Wait for crash
  console.log("Waiting for Fly Step or crash...");
  await new Promise(r => setTimeout(r, 3000));
  
  const bodyHTML = await page.evaluate(() => document.body.innerHTML);
  if (bodyHTML.includes("Something went wrong")) {
      console.log("CRASH DETECTED. Error boundary triggered.");
  } else {
      console.log("No crash detected. UI might be fine.");
  }
  
  await browser.close();
})();
