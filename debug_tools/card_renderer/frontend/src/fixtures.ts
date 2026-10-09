/** Small deterministic fixtures used by the renderer and platform smoke tests. */
export const SAMPLE_A2UI = [
  '{"version":"v0.9","createSurface":{"surfaceId":"weather","catalogId":"ohos.a2ui.extended.catalog.form","width":150,"height":150}}',
  '{"version":"v0.9","updateComponents":{"surfaceId":"weather","root":"root","components":[',
  '{"id":"root","component":"Column","children":["title","main","action"],"itemMargin":6,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"justifyContent":"spaceBetween","linearGradient":{"direction":"RightBottom","colors":[["#86C5E3",0],["#F5DC62",1]]}}},',
  '{"id":"title","component":"Text","content":"天气","styles":{"width":116,"height":20,"fontSize":16,"fontWeight":700,"fontColor":"#E5000000"}},',
  '{"id":"main","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"width":116,"height":48,"fontSize":32,"fontWeight":700,"fontColor":"#E5000000"}},',
  '{"id":"action","component":"Button","label":"查看详情","styles":{"width":116,"height":32,"fontSize":14,"fontColor":"#FFFFFFFF","backgroundColor":"#FF0A59F7","borderRadius":16}}]}}',
  '{"version":"v0.9","updateDataModel":{"surfaceId":"weather","path":"/","value":{"data":{"weather":{"current":{"temperatureText":"26℃"}}}}}}',
].join('');

export const SAMPLE_COMPACT = [
  '["root","Column",{"width":"matchParent","height":150,"padding":12,"borderRadius":18,"clip":true,"space":6,"linearGradient":{"direction":"RightBottom","colors":[["#86C5E3",0],["#F5DC62",1]]},"constraintSize":{"minWidth":140,"maxWidth":140,"minHeight":140,"maxHeight":140}},["title","main","action"]]',
  '["title","Text",{"width":116,"height":20,"content":"青浦天气","fontSize":16,"fontWeight":700,"fontColor":"#E5000000"}]',
  '["main","Text",{"width":116,"height":48,"content":{"path":"/data/weather/current/temperatureText"},"fontSize":32,"fontWeight":700,"fontColor":"#E5000000"}]',
  '["/data/weather/current/temperatureText","29°C"]',
  '["action","Button",{"width":116,"height":30,"label":"天气","fontSize":12,"fontWeight":600,"fontColor":"#FFFFFFFF","backgroundColor":"#FF0A59F7","borderRadius":15}]',
].join('\n');

export const SAMPLE_DESIGN = [
  '["root","Column",{"width":"matchParent","height":150,"padding":12,"borderRadius":18,"clip":true,"space":6,"linearGradient":{"direction":"RightBottom","colors":[["multi_color_aux_02",0],["multi_color_aux_11",1]]},"constraintSize":{"minWidth":140,"maxWidth":140,"minHeight":140,"maxHeight":140}},["title","main","action"]]',
  '["title","Text",{"design":"subtitle-s","width":116,"height":20,"content":"青浦天气","fontColor":"font_primary","maxLines":1}]',
  '["main","Text",{"design":"display-s","width":116,"height":44,"content":{"path":"/data/weather/current/temperatureText"},"fontColor":"font_primary"}]',
  '["/data/weather/current/temperatureText","28°C"]',
  '["action","Button",{"design":"capsule","label":"看天气","backgroundColor":"background_emphasize","fontColor":"font_on_primary"}]',
].join('\n');

