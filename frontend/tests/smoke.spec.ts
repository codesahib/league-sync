import { test, expect } from '@playwright/test';

test('baseline CSV handoff exposes a stale transfer',async({page,request})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Two systems. One reliable roster.'})).toBeVisible();
 await page.getByRole('button',{name:'Save transfer'}).click();
 await expect(page.getByRole('status')).toContainText('Transfer saved');
 const csv=await (await request.get('/api/baseline/export')).text();
 await page.getByLabel('Upload roster CSV').setInputFiles({name:'roster.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
 await expect(page.getByRole('status')).toContainText('CSV imported');
 await expect(page.getByText('duplicate · stale_fields')).toBeVisible();
 await page.screenshot({path:'../evidence/baseline.png',fullPage:true});
 expect(errors).toEqual([]);
});
