// Check the actual shared save guard and demo transition without a DOM/browser package.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const source=fs.readFileSync(fileURLToPath(new URL('../static/app.js',import.meta.url)),'utf8');
const start=source.indexOf('async function waitForSavedAnswers('),end=source.indexOf('function profileBody(');
assert.ok(start>=0&&end>start);
let requests=0;
const context=vm.createContext({saveQueue:Promise.resolve(),saveFailed:true,user:{role:'candidate'},attempt:{id:'unsaved'},questionIndex:0,
 post:async()=>{requests++;return {role:'candidate'};},closeModal(){},go(){},location:{hash:''},render:async()=>{}});
vm.runInContext(source.slice(start,end),context);
await assert.rejects(vm.runInContext('waitForSavedAnswers()',context),/несохранённые/);
await assert.rejects(vm.runInContext("demoLogin('employer')",context),/несохранённые/);
assert.equal(requests,0);assert.equal(context.attempt.id,'unsaved');
let resolveSave;context.saveQueue=new Promise(resolve=>{resolveSave=resolve;});context.saveFailed=false;
const pending=vm.runInContext("demoLogin('employer')",context);
await Promise.resolve();assert.equal(requests,0);
resolveSave();await pending;assert.equal(requests,1);
context.saveFailed=true;
await vm.runInContext("demoLogin('candidate',true)",context);
assert.equal(requests,2);assert.equal(context.saveFailed,false);assert.equal(context.attempt,null);
console.log('Failed/pending saves block transitions; confirmed reset clears the error');
