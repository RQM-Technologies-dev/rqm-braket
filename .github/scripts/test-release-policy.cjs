const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const workflow = readFileSync(join(__dirname, '../workflows/publish.yml'), 'utf8');
// Execute the actual inline workflow policy, not a separate model of it.
const scripts = [...workflow.matchAll(/          script: \|\n((?:            [^\n]*\n)+)/g)]
  .map(match => match[1].split('\n').filter(Boolean).map(line => line.slice(12)).join('\n'));
assert.equal(scripts.length, 3, 'guard, post-approval publication, and attachment must all recheck');
assert.ok(scripts.every(script => script === scripts[0]), 'all live checks must stay identical');
const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
const verify = new AsyncFunction('github', 'context', 'core', scripts[0]);
const SHA = 'a'.repeat(40), MAIN = 'b'.repeat(40), OBJECT = 'c'.repeat(40);
const project = workflow.match(/^  PUBLISH_PROJECT: (.+)$/m)[1];

async function fixture(change = () => {}) {
  const state = {
    context: {repo: {owner: 'RQM-Technologies-dev', repo: project},
      eventName: 'workflow_dispatch', payload: {inputs: {tag_name: 'v1.2.3'}},
      ref: 'refs/tags/v1.2.3', sha: SHA},
    env: {PUBLISH_PROJECT: project, GITHUB_REF_TYPE: 'tag',
      GITHUB_WORKFLOW_REF: `RQM-Technologies-dev/${project}/.github/workflows/publish.yml@refs/tags/v1.2.3`,
      GITHUB_WORKFLOW_SHA: SHA, EXPECTED_RELEASE_ID: ''},
    ref: {ref: 'refs/tags/v1.2.3', object: {type: 'commit', sha: SHA}},
    annotation: {object: {type: 'commit', sha: SHA}},
    release: {id: 123, tag_name: 'v1.2.3', draft: false, prerelease: false,
      published_at: '2026-11-07T12:00:00Z', target_commitish: SHA},
    main: {name: 'main', protected: true, commit: {sha: MAIN}},
    comparison: {status: 'ahead', merge_base_commit: {sha: SHA}},
  };
  change(state);
  const before = {...process.env};
  Object.assign(process.env, state.env);
  const outputs = {};
  try {
    const github = {request: async (route, args) => {
      if (state.apiError) throw new Error('API unavailable');
      assert.equal(args.owner, 'RQM-Technologies-dev');
      assert.equal(args.repo, project);
      if (route.includes('/git/ref/')) { assert.equal(args.ref, 'tags/v1.2.3'); return {data: state.ref}; }
      if (route.includes('/git/tags/')) return {data: state.annotation};
      if (route.includes('/releases/tags/')) { assert.equal(args.tag, 'v1.2.3'); return {data: state.release}; }
      if (route.includes('/branches/')) { assert.equal(args.branch, 'main'); return {data: state.main}; }
      if (route.includes('/compare/')) { assert.equal(args.basehead, `${SHA}...${state.main.commit.sha}`); return {data: state.comparison}; }
      throw new Error(`Unexpected API ${route}`);
    }};
    await verify(github, state.context, {setOutput: (key, value) => {outputs[key] = value;}});
    return outputs;
  } finally {
    for (const key of Object.keys(state.env)) {
      if (before[key] === undefined) delete process.env[key]; else process.env[key] = before[key];
    }
  }
}

test('accepts exact dispatch on protected main history after main advances', async () => {
  assert.deepEqual(await fixture(), {commit: SHA, tag: 'v1.2.3', 'release-id': '123'});
});
test('accepts annotated tags and release-please SHA target_commitish', async () => {
  await fixture(s => {s.ref.object = {type: 'tag', sha: OBJECT};});
});
test('accepts published event with matching release identity and identical main tip', async () => {
  await fixture(s => {
    s.context.eventName = 'release'; s.context.payload = {action: 'published', release: {...s.release}};
    s.main.commit.sha = SHA; s.comparison.status = 'identical';
  });
});
test('accepts final recheck of the same release ID', async () => {
  await fixture(s => {s.env.EXPECTED_RELEASE_ID = '123';});
});

const attacks = {
  'branch dispatch': s => {s.context.ref = 'refs/heads/main'; s.env.GITHUB_REF_TYPE = 'branch';},
  'wrong ref with tag type': s => {s.context.ref = 'refs/tags/v1.2.4';},
  'mismatched input': s => {s.context.payload.inputs.tag_name = 'v1.2.4';},
  'empty tag': s => {s.context.payload.inputs.tag_name = '';},
  'missing tag': s => {delete s.context.payload.inputs.tag_name;},
  'shell injection tag': s => {s.context.payload.inputs.tag_name = 'v1.2.3; echo unsafe';},
  'newline tag': s => {s.context.payload.inputs.tag_name = 'v1.2.3\n';},
  'prerelease tag': s => {s.context.payload.inputs.tag_name = 'v1.2.3rc1';},
  'noncanonical version': s => {s.context.payload.inputs.tag_name = 'v01.2.3';},
  'unexpected event': s => {s.context.eventName = 'pull_request';},
  'wrong workflow ref': s => {s.env.GITHUB_WORKFLOW_REF = 'other';},
  'wrong workflow SHA': s => {s.env.GITHUB_WORKFLOW_SHA = MAIN;},
  'invalid SHA': s => {s.context.sha = s.env.GITHUB_WORKFLOW_SHA = 'nope';},
  'different repository': s => {s.context.repo.repo = 'other';},
  'different owner': s => {s.context.repo.owner = 'other';},
  'moved tag': s => {s.ref.object.sha = MAIN;},
  'wrong API ref': s => {s.ref.ref = 'refs/tags/v1.2.4';},
  'tag points to tree': s => {s.ref.object.type = 'tree';},
  'cyclic annotated tag': s => {s.ref.object = s.annotation.object = {type: 'tag', sha: OBJECT};},
  'wrong release tag': s => {s.release.tag_name = 'v1.2.4';},
  'draft release': s => {s.release.draft = true;},
  'prerelease': s => {s.release.prerelease = true;},
  'unpublished release': s => {s.release.published_at = null;},
  'invalid release ID': s => {s.release.id = '123';},
  'recreated release event': s => {s.context.eventName = 'release'; s.context.payload = {action: 'published', release: {...s.release, id: 124}};},
  'unpublished event': s => {s.context.eventName = 'release'; s.context.payload.action = 'created';},
  'release recreated after validation': s => {s.env.EXPECTED_RELEASE_ID = '124';},
  'unprotected main': s => {s.main.protected = false;},
  'missing main protection': s => {delete s.main.protected;},
  'different main branch': s => {s.main.name = 'other';},
  'diverged release': s => {s.comparison.status = 'diverged';},
  'release ahead of main': s => {s.comparison.status = 'behind';},
  'wrong merge base': s => {s.comparison.merge_base_commit.sha = MAIN;},
  'missing or inaccessible release/API': s => {s.apiError = true;},
};
for (const [name, change] of Object.entries(attacks)) {
  test(`rejects ${name}`, async () => {await assert.rejects(fixture(change));});
}

test('preserves least-privilege publishing and immutable downstream checkouts', () => {
  assert.match(workflow, /name: pypi/);
  assert.match(workflow, /uses: pypa\/gh-action-pypi-publish@release\/v1/);
  assert.match(workflow, /id-token: write/);
  assert.doesNotMatch(workflow, /password:|secrets\./);
  assert.equal((workflow.match(/ref: \$\{\{ needs.guard.outputs.commit \}\}/g) || []).length, 2);
  assert.match(workflow, /needs: \[guard, test\]/);
  assert.equal((workflow.match(/needs: \[guard, build, attest\]/g) || []).length, 2);
  assert.equal((workflow.match(/EXPECTED_RELEASE_ID: \$\{\{ needs.guard.outputs.release-id \}\}/g) || []).length, 2);
  assert.match(workflow, /cancel-in-progress: false/);
});
