// Called by audit_contrast.mjs against a disposable local/demo database.
import assert from 'node:assert/strict';

export async function checkIntegration({ evaluate, visit, send }) {
  const checks = [];
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const wait = async (expression, label) => {
    for (let i = 0; i < 160; i++) {
      if (await evaluate(expression)) return;
      await pause(50);
    }
    throw new Error(
      label +
        ': ' +
        (await evaluate(
          `document.querySelector('#modal[open] .formerror')?.textContent || [...document.querySelectorAll('.formerror')].map(x=>x.textContent).join(' ') || document.querySelector('#toast')?.textContent || document.body.textContent.slice(-500)`
        ))
    );
  };
  const click = (selector) =>
    evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const submit = async (type, values = {}) => {
    await evaluate(
      `(()=>{const f=document.querySelector('form[data-form="${type}"]');for(const [key,value] of Object.entries(${JSON.stringify(values)})){const input=f.elements.namedItem(key);if(input.type==='checkbox')input.checked=value;else input.value=String(value);}if(!f.checkValidity())throw new Error('Invalid form: ${type}');f.requestSubmit();})()`
    );
  };
  const read = (endpoint) =>
    evaluate(
      `fetch('/api${endpoint}').then(async r=>{if(!r.ok)throw new Error(await r.text());return r.json()})`
    );
  const reload = async (selector) => {
    const previous = await evaluate('performance.timeOrigin');
    await send('Page.reload');
    await wait(
      `performance.timeOrigin!==${previous}&&!!document.querySelector(${JSON.stringify(selector)})&&!document.querySelector('.loading-skeleton')`,
      'Reload'
    );
  };
  const switchRole = async (role) => {
    await click('[data-action="demo-switch"]');
    await wait(
      `user?.role===${JSON.stringify(role)}&&!document.querySelector('.loading-skeleton')`,
      'Role switch'
    );
  };
  const deleteAccount = async (password) => {
    await visit('settings');
    await click('[data-action="delete-account"]');
    await submit('delete-account', { password });
    await wait(`user===null&&!!document.querySelector('#public-content')`, 'Account deletion');
    assert.equal(await evaluate(`fetch('/api/auth/me').then(r=>r.status)`), 401);
  };

  await click('[data-action="logout"]');
  await wait('user===null', 'Logout');
  const password = 'Integration2026!';
  for (const role of ['candidate', 'employer']) {
    const email = `integration-${role}-${Date.now()}@example.invalid`;
    await visit('register');
    await click(`[data-action="auth-role"][data-role="${role}"]`);
    await submit('register', {
      name: 'Проверка интеграции',
      email,
      password,
      consent: true,
      terms_accepted: true,
      age_confirmed: true,
    });
    await wait(`!!document.querySelector('.demo-code strong')`, 'Registration');
    const code = await evaluate(`document.querySelector('.demo-code strong').textContent`);
    await submit('verify', { code });
    await wait(
      `user?.role==='${role}'&&!document.querySelector('.loading-skeleton')`,
      'Email verification'
    );
    const privacy = await read('/account/privacy');
    assert.ok(privacy.consent.accepted && privacy.terms.accepted && privacy.age.confirmed);
    const registeredId = (await read('/auth/me')).id;
    await click('[data-action="logout"]');
    await wait('user===null', 'Registered account logout');
    await visit('login');
    await submit('login', { email, password });
    await wait(
      `user?.id===${registeredId}&&!document.querySelector('.loading-skeleton')`,
      'Password login'
    );
    if (role === 'candidate') {
      assert.equal((await read('/candidate/profile')).published, false);
      await visit('profile');
      await submit('fsp-link', { fsp_id: 'FSP-DEMO-001' });
      await wait(
        `!!document.querySelector('#modal[open] form[data-form="fsp-confirm"]')`,
        'FSP ownership form'
      );
      const fspCode = await evaluate(
        `document.querySelector('#modal .demo-code strong').textContent`
      );
      await submit('fsp-confirm', { code: fspCode === '111111' ? '222222' : '111111' });
      await wait(
        `document.querySelector('#modal .formerror')?.textContent.includes('Код неверный')`,
        'Wrong FSP code rejected'
      );
      await submit('fsp-confirm', { code: fspCode });
      await wait(
        `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
        'FSP ownership confirmation'
      );
      assert.equal((await read('/candidate/profile')).fsp_id, 'FSP-DEMO-001');
      await click('[data-action="unlink-fsp"]');
      await wait(
        `!!document.querySelector('form[data-form="fsp-link"]')&&!document.querySelector('.loading-skeleton')`,
        'FSP unlink'
      );
      assert.equal((await read('/candidate/profile')).fsp_id, null);
      checks.push('FSP demo link, rejected code, corrected confirmation and unlink');
      await visit('tests');
      await submit('start-test', { specialization: 'backend', grade: 'Junior' });
      await wait(`!!document.querySelector('[data-answer]')`, 'Test start');
      const answer = await evaluate(
        `(()=>{const input=document.querySelector('[data-answer]');if(input.type==='radio'){input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));}else{input.value='wrong-answer';input.dispatchEvent(new Event('input',{bubbles:true}));}return {id:input.dataset.answer,value:input.value}})()`
      );
      await wait(
        `document.querySelector('#save-state')?.textContent.includes('Все ответы сохранены')`,
        'Answer save'
      );
      assert.equal((await read('/candidate/tests')).active.answers[answer.id], answer.value);
      await reload('[data-answer]');
      assert.equal(
        await evaluate(
          `document.querySelector('[data-answer]:checked')?.value || document.querySelector('[data-answer][type="text"]')?.value`
        ),
        answer.value
      );
      const changeAnswer = (offline) =>
        evaluate(
          `(()=>{const fields=[...document.querySelectorAll('[data-answer]')];const input=fields[${offline ? 'Math.min(1,fields.length-1)' : '0'}];if(input.type==='radio'){input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));}else{input.value=${JSON.stringify(offline ? 'offline-answer' : 'recovered-answer')};input.dispatchEvent(new Event('input',{bubbles:true}));}return {id:input.dataset.answer,value:input.value}})()`
        );
      await send('Network.emulateNetworkConditions', {
        offline: true,
        latency: 0,
        downloadThroughput: -1,
        uploadThroughput: -1,
      });
      try {
        await changeAnswer(true);
        await wait(
          `document.querySelector('#save-state')?.textContent.includes('Не сохранено')`,
          'Failed save is visible'
        );
        await evaluate(`location.hash='profile'`);
        await wait(
          `location.hash==='#tests'&&!!document.querySelector('[data-answer]')`,
          'Failed save blocks navigation'
        );
      } finally {
        await send('Network.emulateNetworkConditions', {
          offline: false,
          latency: 0,
          downloadThroughput: -1,
          uploadThroughput: -1,
        });
      }
      const recovered = await changeAnswer(false);
      await wait(
        `document.querySelector('#save-state')?.textContent.includes('Все ответы сохранены')`,
        'Save recovers after reconnect'
      );
      assert.equal((await read('/candidate/tests')).active.answers[recovered.id], recovered.value);
      await click('[data-action="finish-test"]');
      await wait(
        `!!document.querySelector('[data-action="finish-confirm"]')`,
        'Finish confirmation'
      );
      await click('[data-action="finish-confirm"]');
      await wait(`!!document.querySelector('#modal[open] .resultsummary')`, 'Test result');
      const history = await read('/candidate/tests');
      assert.equal(history.active, null);
      assert.equal(history.history[0].result.total, 15);
      assert.equal(history.history[0].result.passed, false);
      assert.equal((await read('/candidate/profile')).categories.length, 0);
      await click('#modal [data-action="close"]');
      await reload('form[data-form="start-test"]');
      assert.ok(
        await evaluate(
          `document.querySelector('#content').textContent.includes('История попыток')&&!!document.querySelector('[data-action="result"]')`
        )
      );
      checks.push(
        'Registration, email verification, test autosave, reload, finish and persisted result'
      );
      checks.push('Failed autosave blocks navigation and recovers after reconnect');
    } else {
      await visit('company');
      await submit('company', { name: 'Интеграционная компания', contact: 'hr@example.invalid' });
      await wait(
        `document.querySelector('#toast').textContent==='Информация о компании сохранена'&&!document.querySelector('.loading-skeleton')`,
        'Company save'
      );
      await reload('form[data-form="company"]');
      assert.equal((await read('/employer/company')).name, 'Интеграционная компания');
      checks.push('Employer registration and persistent company edit');
    }
    await deleteAccount(password);
  }
  checks.push('Password login and account deletion for both registered roles');

  await visit('login');
  await click('[data-action="auth-role"][data-role="candidate"]');
  await click('[data-action="demo-login"][data-role="candidate"]');
  await wait(`user?.browser_demo&&!document.querySelector('.loading-skeleton')`, 'Personal demo');
  await click('[data-action="demo-reset"]');
  await click('[data-action="demo-reset-confirm"]');
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
    'Reset'
  );
  const candidate = await read('/auth/me');
  await visit('profile');
  await submit('profile', {
    phone: '+7 900 123-45-67',
    telegram: '@integration_check',
    work_format: 'any',
    skills: 'Python, SQL, FastAPI',
    published: true,
  });
  await wait(
    `document.querySelector('#toast').textContent==='Профиль сохранён'&&!document.querySelector('.loading-skeleton')`,
    'Profile save'
  );
  await reload('form[data-form="profile"]');
  assert.equal((await read('/candidate/profile')).contacts.phone, '+7 900 123-45-67');
  checks.push('Candidate profile persists after reload');

  await switchRole('employer');
  await visit('needs');
  await click('[data-action="need-new"]');
  await submit('need', {
    title: 'Интеграционная вакансия',
    description: 'Разработка API и проверка данных на Python и SQL.',
    skills: 'Python, SQL',
    published: true,
    salary_from: 200000,
    salary_to: 100000,
  });
  await wait(
    `document.querySelector('#modal .formerror')?.textContent.includes('Верхняя граница зарплаты меньше нижней')`,
    'Invalid salary rejected'
  );
  assert.ok(!(await read('/employer/needs')).some((n) => n.title === 'Интеграционная вакансия'));
  await submit('need', { salary_to: 260000 });
  checks.push('Server validation appears in the form and corrected salary saves once');
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
    'Need creation'
  );
  const need = (await read('/employer/needs')).find((n) => n.title === 'Интеграционная вакансия');
  assert.ok(need?.published);
  await visit('invitations');
  await click('[data-action="withdraw-invite"]');
  await wait(
    `!document.querySelector('[data-action="withdraw-invite"]')&&!document.querySelector('.loading-skeleton')`,
    'Withdraw seeded invitation'
  );
  await visit('matching');
  await submit('filters', { need: need.id, q: 'Python SQL' });
  await wait(
    `!!document.querySelector('[data-action="candidate-detail"][data-id="${candidate.id}"]')&&!document.querySelector('.loading-skeleton')`,
    'Search'
  );
  const hidden = await read('/employer/candidates/' + candidate.id);
  assert.equal(hidden.contacts_open, false);
  assert.ok(!hidden.contacts?.email && !hidden.contacts?.phone);
  await visit('invitations');
  await click(`[data-action="candidate-detail"][data-id="${candidate.id}"]`);
  await wait(
    `!!document.querySelector('#modal[open] [data-action="invite"]')`,
    'Candidate profile'
  );
  await click(`[data-action="invite"][data-id="${candidate.id}"]`);
  await wait(`!!document.querySelector('#modal[open] form[data-form="invite"]')`, 'Invite form');
  await submit('invite', { title: 'Интеграционное приглашение' });
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
    'Send invitation'
  );
  assert.ok(
    await evaluate(
      `document.querySelector('#content').textContent.includes('Интеграционное приглашение')`
    ),
    'New invitation must appear without reloading'
  );
  const invitation = (await read('/invitations')).find(
    (i) => i.title === 'Интеграционное приглашение'
  );
  assert.ok(invitation);
  await switchRole('candidate');
  await visit('invitations');
  await click(`[data-action="invitation-detail"][data-id="${invitation.id}"]`);
  await wait(`!!document.querySelector('#modal[open]')`, 'Invitation detail');
  assert.equal((await read('/invitations')).find((i) => i.id === invitation.id).status, 'viewed');
  await click('#modal [data-action="close"]');
  assert.ok(
    await evaluate(
      `document.querySelector('[data-action="invitation-detail"][data-id="${invitation.id}"]').closest('article').textContent.includes('Просмотрено')`
    ),
    'UI invitation status must reflect the backend'
  );
  await click(`[data-action="accept-invite"][data-id="${invitation.id}"]`);
  assert.equal(
    await evaluate(`document.querySelector('form[data-form="accept"]').checkValidity()`),
    false
  );
  await submit('accept', { share_contacts: true });
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
    'Accept invitation'
  );
  await switchRole('employer');
  const opened = await read('/employer/candidates/' + candidate.id);
  assert.equal(opened.contacts.phone, '+7 900 123-45-67');
  await click(`[data-action="candidate-detail"][data-id="${candidate.id}"]`);
  await wait(`!!document.querySelector('#modal[open] .contactbox')`, 'Contacts displayed');
  assert.ok(
    await evaluate(
      `document.querySelector('#modal .contactbox').textContent.includes('+7 900 123-45-67')`
    )
  );
  await click('#modal [data-action="close"]');
  await switchRole('candidate');
  await visit('settings');
  await click('[data-action="revoke-contact"]');
  await wait(`!document.querySelector('[data-action="revoke-contact"]')`, 'Revoke contacts');
  await switchRole('employer');
  assert.equal((await read('/employer/candidates/' + candidate.id)).contacts_open, false);
  checks.push(
    'Multiword search, invitation viewed/accepted, explicit contact consent and revocation'
  );

  await switchRole('candidate');
  await visit('jobs');
  await click(`[data-action="job-apply"][data-id="${need.id}"]`);
  await submit('job-apply', { share_contacts: true });
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')&&!document.querySelector('[data-action="job-apply"][data-id="${need.id}"]')`,
    'Application'
  );
  await reload('#content');
  assert.ok((await read('/applications')).some((a) => a.need.id === need.id));
  await switchRole('employer');
  await visit('invitations');
  assert.ok(
    await evaluate(
      `document.querySelector('#content').textContent.includes('Интеграционная вакансия')`
    )
  );
  assert.equal((await read('/employer/candidates/' + candidate.id)).contacts_open, true);
  checks.push('Published vacancy, candidate application and employer visibility');

  await visit('tasks');
  await click('[data-action="task-new"]');
  await submit('task', {
    title: 'Интеграционное задание',
    description: 'Опишите обработку повторных запросов к API и границы транзакции.',
  });
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
    'Task creation'
  );
  assert.ok((await read('/tasks')).some((t) => t.title === 'Интеграционное задание'));

  await switchRole('candidate');
  await visit('tasks');
  const assignment = (await read('/tasks')).find((t) => t.status === 'assigned');
  assert.ok(assignment);
  await submit('task-answer', {
    answer: 'Проверю входные данные, добавлю транзакцию и тесты на повторный запрос.',
  });
  await wait(
    `!document.querySelector('form[data-form="task-answer"]')&&!document.querySelector('.loading-skeleton')`,
    'Task answer'
  );
  await switchRole('employer');
  await visit('tasks');
  await click('[data-action="review-task"]');
  await submit('review', {
    correctness: 2,
    completeness: 2,
    reasoning: 1,
    feedback: 'Хорошее решение. Добавьте описание обработки повторных запросов.',
  });
  await wait(
    `!document.querySelector('#modal[open]')&&!document.querySelector('.loading-skeleton')`,
    'Review'
  );
  await switchRole('candidate');
  await visit('tasks');
  const reviewed = (await read('/tasks')).find((t) => t.id === assignment.id);
  assert.equal(reviewed.status, 'reviewed');
  assert.equal(reviewed.answer.score, 83);
  assert.ok(
    await evaluate(
      `document.querySelector('#content').textContent.includes('83%')&&document.querySelector('#content').textContent.includes('Хорошее решение')`
    )
  );
  await reload('#content');
  await click('[data-action="notifications"]');
  await wait(`!!document.querySelector('#modal[open] .notification')`, 'Notifications');
  await click('[data-action="read-notifications"]');
  await wait(`!document.querySelector('#modal[open]')`, 'Mark notifications read');
  assert.ok((await read('/notifications')).every((n) => n.seen));
  checks.push(
    'Task creation, assigned task answer, employer review, persistent score and notifications'
  );

  await visit('settings');
  await click('[data-action="toggle-publication"]');
  await wait(
    `document.querySelector('#content')?.textContent.includes('Профиль скрыт')&&!document.querySelector('.loading-skeleton')`,
    'Hide profile'
  );
  await switchRole('employer');
  assert.ok(!(await read('/employer/candidates')).candidates.some((p) => p.id === candidate.id));
  await switchRole('candidate');
  await visit('settings');
  await click('[data-action="toggle-publication"]');
  await wait(
    `document.querySelector('#content')?.textContent.includes('Профиль опубликован')&&!document.querySelector('.loading-skeleton')`,
    'Publish profile'
  );
  await switchRole('employer');
  assert.ok((await read('/employer/candidates')).candidates.some((p) => p.id === candidate.id));
  checks.push('Publication controls affect employer search');
  return checks;
}
