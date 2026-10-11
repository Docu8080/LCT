// Optional independent execution check; Node.js is not needed to run the app.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const result=spawnSync(process.env.PYTHON||path.join(root,'.venv/bin/python'),['-c',`from assessment import generate,GRADES
import json
print(json.dumps([q for g in GRADES for s in range(30) for q in generate('frontend',g,s) if q['skill']=='JavaScript']))`],{cwd:root,encoding:'utf8'});
assert.equal(result.status,0,result.stderr);
const cases=JSON.parse(result.stdout);
for(const q of cases){let output='';vm.runInNewContext(q.code,{console:{log:(value)=>{output+=String(value)}},setTimeout,Promise});await new Promise(resolve=>setTimeout(resolve,2));assert.equal(output,q.answer,q.code);}
console.log(`${cases.length} generated JavaScript answers verified by execution`);

