import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
const python = resolve('..', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) throw new Error('Create the repository .venv first.');
export default defineConfig({
 testDir:'tests', workers:1, fullyParallel:false, timeout:30000,
 reporter:[['list'], ['json',{outputFile:'../evidence/ui-results.json'}]],
 use:{baseURL:'http://127.0.0.1:5183',viewport:{width:1440,height:1100},trace:'retain-on-failure',
  ...(process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {})},
 webServer:[
  {command:`"${python}" ../scripts/serve-test.py`,url:'http://127.0.0.1:8011/api/health',reuseExistingServer:false},
  {command:'npm run dev',url:'http://127.0.0.1:5183',reuseExistingServer:false,
   env:{FRONTEND_PORT:'5183',VITE_API_TARGET:'http://127.0.0.1:8011'}}
 ]
});
