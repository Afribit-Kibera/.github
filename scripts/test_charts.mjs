import assert from 'node:assert/strict';
import { test } from 'node:test';
import { activity, codeMix, languageBuckets, palettes, renderChart } from './render_charts.mjs';

const names = ['Taka Sats', '3 West Satenet', 'Afribitools', 'BTCReg', 'Website & Bitcoin Studio', 'Afribit NFC'];
const fixture = {
  original_repositories: 6,
  languages: { TypeScript: 900, JavaScript: 40, CSS: 25, Python: 20, HTML: 10, Shell: 4, Dockerfile: 1 },
  repositories: [...names.map((project, index) => ({ name: index === 4 ? 'Website' : `project-${index}`, project, fork: false, languages: { TypeScript: 150, CSS: 50 } })), { name: 'wallet', fork: true }],
  activity: {
    complete: true,
    weeks: Array.from({ length: 12 }, (_, index) => ({ week: new Date(Date.UTC(2026, 7, 2 + 7 * index)).toISOString().slice(0, 10), commits: index * 6 })),
    repositories: names.map((project, index) => ({ repository: `project-${index}`, project, commits: Array.from({ length: 12 }, (_, col) => col) })),
  },
};

test('language buckets preserve every byte and group only the tail', () => {
  const buckets = languageBuckets(fixture.languages);
  assert.equal(buckets.length, 6);
  assert.deepEqual(buckets.at(-1), { name: 'Other', value: 5 });
  assert.equal(buckets.reduce((total, item) => total + item.value, 0), 1000);
});

test('each project ring compares its leading language with the remainder', () => {
  const chart = codeMix(fixture, 'light', false);
  assert.equal(chart.option.series.length, 7);
  assert.deepEqual(chart.option.series[1].data.map(item => item.value), [150, 50]);
  assert.equal(chart.option.series[0].data.reduce((total, item) => total + item.value, 0), 1000);
});

test('trend is unsmoothed with a zero baseline and exact source values', () => {
  const chart = activity(fixture, 'light', false);
  assert.equal(chart.option.yAxis[0].min, 0);
  assert.equal(chart.option.series[0].smooth, false);
  assert.deepEqual(chart.option.series[0].data, fixture.activity.weeks.map(week => week.commits));
  const heat = chart.option.series[1].data;
  for (let week = 0; week < 12; week++) {
    assert.equal(heat.filter(item => item.value[0] === week).reduce((total, item) => total + item.value[2], 0), fixture.activity.weeks[week].commits);
  }
});

test('mobile heatmap retains all six repositories and twelve weeks', () => {
  const chart = activity(fixture, 'dark', true);
  assert.equal(chart.option.series.length, 7);
  chart.option.series.slice(1).forEach((row, index) => {
    assert.equal(row.data.length, 12);
    assert.deepEqual(row.data.map(item => item.value[2]), fixture.activity.repositories[index].commits);
  });
});

test('unavailable activity is a message, never a zero-valued chart', () => {
  const incomplete = structuredClone(fixture);
  incomplete.activity = { complete: false, weeks: [], repositories: [] };
  const chart = activity(incomplete, 'dark', true);
  assert.equal(chart.option.series.length, 0);
  assert.match(renderChart(chart).svg, /activity is unavailable/);
});

test('all variants render script-free, motion-free vector charts', () => {
  for (const theme of Object.keys(palettes)) {
    for (const mobile of [false, true]) {
      for (const chart of [codeMix(fixture, theme, mobile), activity(fixture, theme, mobile)]) {
        const { svg } = renderChart(chart);
        assert.match(svg, /<svg/);
        assert.match(svg, /<path/);
        assert.doesNotMatch(svg, /NaN|Infinity|<script|<image|@keyframes|<animate|https?:\/\/(?!www\.w3\.org)/);
        assert.equal(chart.option.animation, false);
      }
    }
  }
});

test('empty source data does not produce invalid geometry', () => {
  const empty = structuredClone(fixture);
  empty.languages = {};
  empty.repositories = [];
  assert.doesNotMatch(renderChart(codeMix(empty, 'light', true)).svg, /NaN|Infinity/);
});
