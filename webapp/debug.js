import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  page.on('console', msg => console.log('BROWSER_LOG:', msg.text()));
  page.on('pageerror', error => console.log('BROWSER_ERROR:', error.message));

  const wait = (ms) => new Promise(r => setTimeout(r, ms));

  console.log('Navigating to login...');
  await page.goto('http://localhost:5173/login');
  
  console.log('Clicking surveyor login...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const surveyorBtn = btns.find(b => b.textContent.includes('surveyor'));
    if (surveyorBtn) surveyorBtn.click();
  });

  await wait(2000);

  console.log('Clicking on case AP-07...');
  await page.evaluate(() => {
    const tds = Array.from(document.querySelectorAll('td'));
    const ap07 = tds.find(t => t.textContent.includes('AP-07'));
    if (ap07) {
      const row = ap07.closest('tr');
      row.querySelector('button').click();
    }
  });

  await wait(2000);

  console.log('Approving boundary...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const approve = btns.find(b => b.textContent.includes('Approve Boundary'));
    if (approve) approve.click();
  });
  
  await wait(1000);

  console.log('Proceeding to plan...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const proceed = btns.find(b => b.textContent.includes('Proceed to Plan'));
    if (proceed) proceed.click();
  });

  await wait(2000);

  console.log('Locking plan...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const lock = btns.find(b => b.textContent.includes('Lock Plan'));
    if (lock) lock.click();
  });

  await wait(2000);
  console.log('Done!');
  await browser.close();
})();
