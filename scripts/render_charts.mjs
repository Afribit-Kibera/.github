import * as echarts from 'echarts';
import { pathToFileURL } from 'node:url';

const FONT = 'Arial, Helvetica, sans-serif';
export const palettes = {
  light: { bg: '#F6F9F8', ink: '#15231D', muted: '#53655D', line: '#D6E1DA', accent: '#146A48', track: '#E2EAE6', low: '#D6EAF5', mid: '#9CCBE8', high: '#1764A5' },
  dark: { bg: '#101C17', ink: '#F4F8F5', muted: '#B5C6BC', line: '#35483D', accent: '#7ED7A5', track: '#2A3B31', low: '#203C4A', mid: '#22516D', high: '#2B78B5' },
};
const colors = { TypeScript: '#438FD3', JavaScript: '#D6AD23', Python: '#31A7B5', CSS: '#A881D6', 'RouterOS Script': '#43B783', HTML: '#E78059', Other: '#899995' };
const color = name => colors[name] ?? colors.Other;
const sum = values => values.reduce((total, value) => total + value, 0);
const percent = (part, whole) => whole ? 100 * part / whole : 0;
const date = week => new Date(`${week}T00:00:00Z`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' });

function text(x, y, value, size, fill, weight = 400, align = 'left') {
  return { type: 'text', silent: true, x, y, style: { text: String(value), font: `${weight} ${size}px ${FONT}`, fill, align, verticalAlign: 'middle' } };
}

function line(x1, y1, x2, y2, p) {
  return { type: 'line', silent: true, shape: { x1, y1, x2, y2 }, style: { stroke: p.line, lineWidth: 1 } };
}

function base(theme, width, height, title, description) {
  return { width, height, title, description, option: { animation: false, backgroundColor: palettes[theme].bg, textStyle: { fontFamily: FONT }, tooltip: { show: false }, series: [], graphic: [] } };
}

export function languageBuckets(values) {
  const sorted = Object.entries(values).sort((a, b) => b[1] - a[1]);
  const top = sorted.slice(0, 5).map(([name, value]) => ({ name, value }));
  const rest = sum(sorted.slice(5).map(([, value]) => value));
  return rest ? [...top, { name: 'Other', value: rest }] : top;
}

function ring(center, radius, values, p, remainder = false) {
  return {
    type: 'pie', silent: true, center, radius, startAngle: 90, clockwise: true,
    label: { show: false }, labelLine: { show: false }, emphasis: { disabled: true },
    itemStyle: { borderColor: p.bg, borderWidth: 2 },
    data: values.map((item, index) => ({ ...item, itemStyle: { color: remainder && index === 1 ? p.track : color(item.name) } })),
  };
}

export function codeMix(data, theme, mobile) {
  const p = palettes[theme];
  const width = mobile ? 360 : 900;
  const height = mobile ? 1140 : 822;
  const pad = mobile ? 24 : 32;
  const chart = base(theme, width, height, 'Public code mix', 'Language shares of detected public source bytes. Each project ring shows its leading language versus all its other languages. Private code and the Blink fork are excluded.');
  const { graphic, series } = chart.option;
  graphic.push(text(pad, 38, 'Inside the code', 26, p.ink, 700), text(pad, 68, 'Public source, measured by language.', mobile ? 15 : 17, p.muted));
  const total = sum(Object.values(data.languages));
  const buckets = languageBuckets(data.languages);
  const cx = mobile ? 180 : 210;
  const cy = mobile ? 211 : 224;
  if (total) series.push(ring([cx, cy], mobile ? [75, 101] : [83, 113], buckets, p));
  graphic.push(text(cx, cy - 12, Object.keys(data.languages).length, 38, p.ink, 700, 'center'), text(cx, cy + 24, 'languages', 16, p.muted, 400, 'center'));
  for (const [index, item] of buckets.entries()) {
    const x = mobile ? 28 + index % 2 * 164 : 398 + index % 2 * 248;
    const y = (mobile ? 350 : 146) + Math.floor(index / 2) * (mobile ? 53 : 68);
    graphic.push({ type: 'circle', silent: true, shape: { cx: x, cy: y, r: 4 }, style: { fill: color(item.name) } });
    graphic.push(text(x + 12, y, item.name, mobile ? 13 : 16, p.ink), text(x + 12, y + 21, `${percent(item.value, total).toFixed(1)}%`, mobile ? 15 : 20, p.ink, 700));
  }
  const divider = mobile ? 498 : 378;
  graphic.push(line(pad, divider, width - pad, divider, p), text(pad, divider + 31, 'Leading language by project', mobile ? 18 : 20, p.ink, 700));
  const originals = data.repositories.filter(repo => !repo.fork);
  for (const [index, repo] of originals.entries()) {
    const [name, bytes] = Object.entries(repo.languages).sort((a, b) => b[1] - a[1])[0] ?? ['No source', 0];
    const allBytes = sum(Object.values(repo.languages));
    const x = mobile ? 100 + index % 2 * 160 : 170 + index % 3 * 280;
    const y = (mobile ? 606 : 493) + Math.floor(index / (mobile ? 2 : 3)) * (mobile ? 170 : 171);
    if (allBytes) series.push(ring([x, y], [37, 48], [{ name, value: bytes }, { name: 'Other', value: allBytes - bytes }], p, true));
    graphic.push(text(x, y, `${percent(bytes, allBytes).toFixed(0)}%`, 22, p.ink, 700, 'center'));
    const label = repo.name === 'Website' ? 'Website & Studio' : repo.project;
    graphic.push(text(x, y + 66, label, mobile ? 14 : 17, p.ink, 700, 'center'), text(x, y + 88, name, mobile ? 13 : 15, p.muted, 400, 'center'));
  }
  graphic.push(text(pad, height - 26, mobile ? 'Language bytes, not authorship or impact.' : 'GitHub Linguist source bytes. Private code and fork history excluded.', mobile ? 13 : 15, p.muted));
  return chart;
}

export function activity(data, theme, mobile) {
  const p = palettes[theme];
  const width = mobile ? 360 : 900;
  const pad = mobile ? 24 : 32;
  const available = data.activity.complete && data.activity.weeks.length > 0;
  const height = available ? mobile ? 1040 : 772 : mobile ? 290 : 260;
  const chart = base(theme, width, height, 'Public build activity', 'Twelve weeks of non-merge commits across original public projects. The line shows weekly totals and the heatmap shows exact repository counts. The latest week is partial. Counts include all commit authors, not just displayed contributors.');
  const { graphic, series } = chart.option;
  graphic.push(text(pad, 38, 'The build rhythm', 26, p.ink, 700), text(pad, 68, '12 weeks of public project activity.', mobile ? 15 : 17, p.muted));
  if (!available) {
    graphic.push(text(pad, 132, 'Public activity is unavailable.', mobile ? 17 : 20, p.ink, 700), text(pad, 170, 'Incomplete totals are not displayed.', mobile ? 14 : 17, p.muted));
    return chart;
  }
  const weeks = data.activity.weeks;
  const rows = data.activity.repositories;
  const counts = weeks.map(week => week.commits);
  const summaries = [[sum(counts), 'Commits'], [counts.filter(value => value > 0).length, 'Active weeks'], [data.original_repositories, 'Public projects']];
  for (const [index, [value, label]] of summaries.entries()) {
    const x = pad + index * (mobile ? 106 : 284);
    graphic.push(text(x, 120, value, mobile ? 30 : 36, p.ink, 700), text(x, 151, label, mobile ? 13 : 16, p.muted));
  }
  const axisText = { color: p.muted, fontFamily: FONT, fontSize: mobile ? 11 : 14 };
  chart.option.grid = [{ left: mobile ? 48 : 64, right: pad, top: 210, height: 150 }];
  chart.option.xAxis = [{ type: 'category', boundaryGap: false, data: weeks.map(week => week.week), axisLine: { lineStyle: { color: p.line } }, axisTick: { show: false }, axisLabel: { ...axisText, margin: 14, interval: (index) => [0, Math.floor(weeks.length / 2), weeks.length - 1].includes(index), formatter: value => date(value), showMinLabel: true, showMaxLabel: true } }];
  chart.option.yAxis = [{ type: 'value', min: 0, minInterval: 1, splitNumber: 3, axisLabel: axisText, splitLine: { lineStyle: { color: p.line, type: 'dashed' } } }];
  graphic.push(text(pad, 190, 'NON-MERGE COMMITS / WEEK', mobile ? 11 : 13, p.muted, 700));
  series.push({ type: 'line', silent: true, smooth: false, data: counts, symbol: 'circle', symbolSize: mobile ? 6 : 8, lineStyle: { color: p.accent, width: 3 }, itemStyle: { color: p.accent, borderColor: p.bg, borderWidth: 2 }, areaStyle: { color: p.accent, opacity: 0.10 }, emphasis: { disabled: true } });
  graphic.push(line(pad, 416, width - pad, 416, p), text(pad, 449, 'Where the work happened', mobile ? 19 : 21, p.ink, 700));
  const heatSeries = [];
  if (mobile) {
    for (const [index, row] of rows.entries()) {
      const y = 510 + index * 65;
      graphic.push(text(pad, y, row.project, 15, p.ink, 700));
      chart.option.grid.push({ left: pad, right: pad, top: y + 15, height: 24 });
      chart.option.xAxis.push({ gridIndex: index + 1, type: 'category', data: weeks.map(week => week.week), show: false });
      chart.option.yAxis.push({ gridIndex: index + 1, type: 'category', data: [row.project], show: false });
      heatSeries.push({ type: 'heatmap', xAxisIndex: index + 1, yAxisIndex: index + 1, data: row.commits.map((count, col) => heatCell(col, 0, count, p)), ...heatStyle(p, mobile) });
    }
    graphic.push(text(pad, 480, date(weeks[0].week), 12, p.muted), text(width - pad, 480, `${date(weeks.at(-1).week)} *`, 12, p.muted, 400, 'right'));
  } else {
    chart.option.grid.push({ left: 178, right: pad, top: 486, height: 204 });
    chart.option.xAxis.push({ gridIndex: 1, type: 'category', data: weeks.map(week => week.week), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { ...axisText, fontSize: 12, interval: 1, formatter: value => date(value), margin: 14 } });
    chart.option.yAxis.push({ gridIndex: 1, type: 'category', inverse: true, data: rows.map(row => row.project), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: p.ink, fontFamily: FONT, fontSize: 14, margin: 12 } });
    heatSeries.push({ type: 'heatmap', xAxisIndex: 1, yAxisIndex: 1, data: rows.flatMap((row, y) => row.commits.map((count, x) => heatCell(x, y, count, p))), ...heatStyle(p, mobile) });
  }
  chart.option.visualMap = { show: false, type: 'piecewise', seriesIndex: heatSeries.map((_, index) => series.length + index), pieces: [{ value: 0, color: p.track }, { min: 1, max: 4, color: p.low }, { min: 5, max: 14, color: p.mid }, { min: 15, color: p.high }] };
  series.push(...heatSeries);
  const keyY = mobile ? 942 : 735;
  for (const [index, [label, fill]] of [['- = 0', p.track], ['1-4', p.low], ['5-14', p.mid], ['15+', p.high]].entries()) {
    const x = pad + index * (mobile ? 77 : 94);
    graphic.push({ type: 'rect', silent: true, shape: { x, y: keyY - 7, width: 12, height: 12, r: 2 }, style: { fill } }, text(x + 18, keyY, label, 12, p.muted));
  }
  if (mobile) {
    graphic.push(text(pad, 981, '* Latest week is partial.', 13, p.muted), text(pad, 1009, 'Private source and fork history excluded.', 13, p.muted));
  } else {
    graphic.push(text(width - pad, keyY, 'Latest week partial. Private source and forks excluded.', 13, p.muted, 400, 'right'));
  }
  return chart;
}

function heatCell(x, y, value, p) {
  return { value: [x, y, value], label: { color: value >= 15 ? '#FFFFFF' : value === 0 ? p.muted : p.ink } };
}

function heatStyle(p, mobile) {
  return { silent: true, itemStyle: { borderColor: p.bg, borderWidth: mobile ? 3 : 4, borderRadius: 3 }, label: { show: true, fontFamily: FONT, fontSize: mobile ? 11 : 13, formatter: params => params.value[2] || '-' }, emphasis: { disabled: true } };
}

export function renderChart(chart) {
  const instance = echarts.init(null, null, { renderer: 'svg', ssr: true, width: chart.width, height: chart.height });
  try {
    instance.setOption(chart.option);
    return { title: chart.title, description: chart.description, svg: instance.renderToSVGString() };
  } finally {
    instance.dispose();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  const data = JSON.parse(input);
  const output = {};
  for (const theme of Object.keys(palettes)) {
    for (const mobile of [false, true]) {
      const suffix = `${mobile ? 'mobile' : 'desktop'}-${theme}.svg`;
      output[`code-mix-${suffix}`] = renderChart(codeMix(data, theme, mobile));
      output[`activity-${suffix}`] = renderChart(activity(data, theme, mobile));
    }
  }
  process.stdout.write(JSON.stringify(output));
}
