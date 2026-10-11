// Check the actual shared save guard and demo transition without a DOM/browser package.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
const source = fs.readFileSync(fileURLToPath(new URL('../static/app.js', import.meta.url)), 'utf8');
const start = source.indexOf('async function waitForSavedAnswers('),
  end = source.indexOf('function profileBody(');
assert.ok(start >= 0 && end > start);
let requests = 0;
const context = vm.createContext({
  saveQueue: Promise.resolve(),
  saveFailed: true,
  user: { role: 'candidate' },
  attempt: { id: 'unsaved' },
  questionIndex: 0,
  post: async () => {
    requests++;
    return { role: 'candidate' };
  },
  closeModal() {},
  go() {},
  location: { hash: '' },
  render: async () => {},
});
vm.runInContext(source.slice(start, end), context);
await assert.rejects(vm.runInContext('waitForSavedAnswers()', context), /несохранённые/);
await assert.rejects(vm.runInContext("demoLogin('employer')", context), /несохранённые/);
assert.equal(requests, 0);
assert.equal(context.attempt.id, 'unsaved');
let resolveSave;
context.saveQueue = new Promise((resolve) => {
  resolveSave = resolve;
});
context.saveFailed = false;
const pending = vm.runInContext("demoLogin('employer')", context);
await Promise.resolve();
assert.equal(requests, 0);
resolveSave();
await pending;
assert.equal(requests, 1);
context.saveFailed = true;
await vm.runInContext("demoLogin('candidate',true)", context);
assert.equal(requests, 2);
assert.equal(context.saveFailed, false);
assert.equal(context.attempt, null);
const page = { innerHTML: 'unsaved answer', focus() {} };
let restoredLocation;
Object.assign(context, {
  route: 'tests',
  attempt: { id: 'unsaved' },
  saveFailed: true,
  renderGeneration: 0,
  timer: null,
  getRoute: () => 'profile',
  clearInterval() {},
  history: {
    replaceState: (_state, _title, url) => {
      restoredLocation = url;
    },
  },
  toast() {},
  document: {},
  window: { scrollTo() {} },
  publicTitles: {},
  candidateNav: [['profile', 'Profile']],
  employerNav: [],
  $: () => page,
  shell: () => {
    page.innerHTML = 'loading';
  },
});
for (const name of [
  'overview',
  'profilePage',
  'testsPage',
  'matchingPage',
  'needsPage',
  'invitationsPage',
  'companyPage',
  'tasksPage',
  'jobsPage',
  'settingsPage',
]) {
  context[name] = async () => 'server response';
}
const renderStart = source.indexOf('async function render(');
const renderEnd = source.indexOf('async function login(');
assert.ok(renderStart >= 0 && renderEnd > renderStart);
vm.runInContext(source.slice(renderStart, renderEnd), context);
await vm.runInContext('render()', context);
assert.equal(context.route, 'tests');
assert.equal(page.innerHTML, 'unsaved answer');
assert.equal(restoredLocation, '#tests');
console.log(
  'Failed saves preserve the test across role changes and navigation; reset clears the error'
);
