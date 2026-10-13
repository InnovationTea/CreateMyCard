# A2UI Markdown Input Example — 旅游攻略落地页

This example shows how a Markdown travel guide can be turned into a polished, web-like information UI (HarmonyOS-styled) while still outputting A2UI v0.9 NDJSON.

## What this example demonstrates

- **Input→UI mapping (Mode A)**: Given a single Markdown document, map its structure (H1/H2/H3, lists, callouts) into an **Info Page** UI.
- **Page Type**: This should be treated as an **Info Page** (reading-first). Paragraphs are not meant to be hard-truncated into tiny cards.
- **Style approach**: Use a small number of high-quality color anchors (chips / section tints) + Harmony grayscale body text. Avoid “flat admin web” look.
- **Output discipline**: Still output strict A2UI v0.9 NDJSON (one component per `updateComponents` line).

## Mapping notes (practical rules)

- **H1** → Hero card title (`hero_title`), with a short kicker chip (`hero_kicker`) and meta chips (season/duration/style).
- **H2 sections** → One section card each (`weather_card`, `transport_card`, ...), each with a title row (mark + title + tag).
- **Bullets / numbered items** → Compact rows or text blocks; keep spacing on 4vp grid (8/12).
- **Callouts (`> ...`)** → A tinted card (light primary tint) with a small mark and readable text (do not overuse ellipsis).

## Input (Markdown)

```markdown
# 东京 3 天游玩攻略（第一次去也能照着走）

## 概览

- 适合季节：3–4 月 / 10–11 月
- 建议时长：3 天
- 风格：Citywalk + 美食 + 经典打卡

## 天气（本周）

- 周三：16–22°C，多云
- 周四：14–20°C，小雨
- 周五：15–21°C，晴

## 如何到达

- 机场到市区：成田 → 东京站（N’EX 约 60–70 分钟）/ 羽田 → 东京站（单轨+JR 约 35–45 分钟）
- 交通卡：Suica / PASMO（刷卡/手机都可）

## 市内交通

- JR 山手线：第一次来最省心的环线
- 地铁：跨区更快
- 步行：每天 1.2–1.8 万步，鞋要舒服

## 必去景点

1. 浅草（浅草寺）— 经典江户风
2. 涩谷 — 十字路口 + 夜生活
3. 上野公园 — 博物馆 +（季节）赏樱
4. teamLab Planets — 沉浸式艺术（建议提前预约）

## 3 天游玩路线

### Day 1 — 浅草 → 上野

- 上午：浅草寺 + 仲见世通
- 中午：上野博物馆区
- 晚上：阿美横丁吃喝逛

### Day 2 — 涩谷 → 原宿

- 上午：明治神宫
- 中午：竹下通 + 表参道
- 晚上：SHIBUYA SKY 看日落

### Day 3 — 台场 + teamLab

- 上午：台场海边散步
- 下午：teamLab Planets（一定要提前订）
- 晚上：银座散步

## 预算（人均/天）

- 交通：¥1,000–¥1,800
- 吃饭：¥2,500–¥5,000
- 门票：¥2,000–¥4,500
- 合计：约 ¥6,000–¥11,000

## 小贴士

> 门票尽量线上提前买；避开高峰（07:30–09:30，17:00–19:00）。
```

## Output (A2UI v0.9 NDJSON)

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"md_travel","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"root","component":"Extended.Column","children":["travel_header","page"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"travel_header","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"旅游攻略"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"page","component":"Extended.Column","children":["hero","weather_card","transport_card","spots_card","itinerary_card","budget_card","tips_card"],"space":12,"styles":{"width":"matchParent","padding":{"top":0,"right":0,"bottom":0,"left":0}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"hero","component":"Extended.Column","children":["hero_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12},"shadow":{"type":"outerDefaultSM"}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"hero_body","component":"Extended.Column","children":["hero_title","hero_sub","hero_chips"],"space":10,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"hero_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":2,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"东京 3 天游玩攻略（第一次去也能照着走）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"hero_sub","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":3,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"Citywalk + 美食 + 经典景点，一页看懂天气、交通、行程与预算。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"hero_chips","component":"Extended.Row","children":["chip_season","chip_duration","chip_style"],"space":8,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"chip_season","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#66000000","backgroundColor":"#FFFFFFFF"},"content":"季节 3–4/10–11月"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"chip_duration","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#66000000","backgroundColor":"#FFFFFFFF"},"content":"时长 3天"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"chip_style","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#66000000","backgroundColor":"#FFFFFFFF"},"content":"玩法 Citywalk+美食"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_card","component":"Extended.Column","children":["weather_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#DCE7FF","shadow":{"type":"outerDefaultSM"}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_body","component":"Extended.Column","children":["weather_head","weather_rows"],"space":10,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_head","component":"Extended.Row","children":["weather_left","weather_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_left","component":"Extended.Row","children":["weather_mark","weather_h"],"space":6,"styles":{"alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_mark","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7"},"content":"▍"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_h","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"天气（本周）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_tag","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#DCE7FF","backgroundColor":"#F7F9FF"},"content":"出行建议"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"weather_rows","component":"Extended.Column","children":["w1","w2","w3"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w1","component":"Extended.Row","children":["w1_day","w1_desc"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w1_day","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"周三"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w1_desc","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","textAlign":"end"},"content":"16–22°C · 多云"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w2","component":"Extended.Row","children":["w2_day","w2_desc"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w2_day","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"周四"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w2_desc","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","textAlign":"end"},"content":"14–20°C · 小雨"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w3","component":"Extended.Row","children":["w3_day","w3_desc"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w3_day","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"周五"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"w3_desc","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","textAlign":"end"},"content":"15–21°C · 晴"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_card","component":"Extended.Column","children":["transport_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#F3FAF5","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#D6F2DD","shadow":{"type":"outerDefaultSM"}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_body","component":"Extended.Column","children":["transport_head","transport_bullets"],"space":10,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_head","component":"Extended.Row","children":["transport_left","transport_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_left","component":"Extended.Row","children":["transport_mark","transport_h"],"space":6,"styles":{"alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_mark","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#2E7D32"},"content":"▍"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_h","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"交通与出行"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_tag","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#2E7D32","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#D6F2DD","backgroundColor":"#F3FAF5"},"content":"省心路线"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"transport_bullets","component":"Extended.Column","children":["tb1","tb2","tb3"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tb1","component":"Extended.Row","children":["tbd1","tbt1"],"space":10,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tbd1","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7"},"content":"●"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tbt1","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000","layoutWeight":1},"content":"Suica / PASMO：刷卡/手机都可，地铁/JR 通用。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tb2","component":"Extended.Row","children":["tbd2","tbt2"],"space":10,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tbd2","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7"},"content":"●"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tbt2","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000","layoutWeight":1},"content":"JR 山手线：第一次来最省心的环线。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tb3","component":"Extended.Row","children":["tbd3","tbt3"],"space":10,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tbd3","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7"},"content":"●"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tbt3","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000","layoutWeight":1},"content":"每天 1.2–1.8 万步：鞋要舒服，雨伞随身。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_card","component":"Extended.Column","children":["spots_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#FFF8E1","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#FFE3A3","shadow":{"type":"outerDefaultSM"}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_body","component":"Extended.Column","children":["spots_head","spots_list"],"space":10,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_head","component":"Extended.Row","children":["spots_left","spots_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_left","component":"Extended.Row","children":["spots_mark","spots_h"],"space":6,"styles":{"alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_mark","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#B45309"},"content":"▍"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_h","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"必去景点"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_tag","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#B45309","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#FFE3A3","backgroundColor":"#FFF8E1"},"content":"经典必打卡"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"spots_list","component":"Extended.Column","children":["s1","s2","s3","s4"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"s1","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"1. 浅草（浅草寺）— 经典江户风"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"s2","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"2. 涩谷 — 十字路口 + 夜生活"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"s3","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"3. 上野公园 — 博物馆 +（季节）赏樱"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"s4","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"4. teamLab Planets — 沉浸式艺术（建议提前预约）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"itinerary_card","component":"Extended.Column","children":["itinerary_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12},"shadow":{"type":"outerDefaultSM"}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"itinerary_body","component":"Extended.Column","children":["it_head","day1","day2","day3"],"space":12,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"it_head","component":"Extended.Row","children":["it_left","it_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"it_left","component":"Extended.Row","children":["it_mark","it_h"],"space":6,"styles":{"alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"it_mark","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7"},"content":"▍"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"it_h","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"3 天游玩路线"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"it_tag","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#DCE7FF","backgroundColor":"#EEF4FF"},"content":"按天照着走"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"day1","component":"Extended.Column","children":["d1_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#F8FAFA","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#33000000"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d1_body","component":"Extended.Column","children":["d1_t","d1_a","d1_b","d1_c"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d1_t","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Day 1 — 浅草 → 上野"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d1_a","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"上午：浅草寺 + 仲见世通"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d1_b","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"中午：上野博物馆区"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d1_c","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"晚上：阿美横丁吃喝逛"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"day2","component":"Extended.Column","children":["d2_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#F8FAFA","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#33000000"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d2_body","component":"Extended.Column","children":["d2_t","d2_a","d2_b","d2_c"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d2_t","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Day 2 — 涩谷 → 原宿"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d2_a","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"上午：明治神宫"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d2_b","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"中午：竹下通 + 表参道"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d2_c","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"晚上：SHIBUYA SKY 看日落"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"day3","component":"Extended.Column","children":["d3_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#F8FAFA","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#33000000"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d3_body","component":"Extended.Column","children":["d3_t","d3_a","d3_b","d3_c"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d3_t","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Day 3 — 台场 + teamLab"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d3_a","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"上午：台场海边散步"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d3_b","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"下午：teamLab Planets（一定要提前订）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"d3_c","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"晚上：银座散步"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_card","component":"Extended.Column","children":["budget_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#FFFBEB","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#F2E6B3","shadow":{"type":"outerDefaultSM"}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_body","component":"Extended.Column","children":["budget_head","budget_rows","budget_total"],"space":10,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_head","component":"Extended.Row","children":["budget_left","budget_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_left","component":"Extended.Row","children":["budget_mark","budget_h"],"space":6,"styles":{"alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_mark","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#C9A227"},"content":"▍"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_h","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"预算（人均/天）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_tag","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#C9A227","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#F2E6B3","backgroundColor":"#FFFBEB"},"content":"费用区间"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_rows","component":"Extended.Column","children":["br1","br2","br3"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br1","component":"Extended.Row","children":["br1_l","br1_r"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br1_l","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"交通"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br1_r","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","textAlign":"end"},"content":"¥1,000–¥1,800"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br2","component":"Extended.Row","children":["br2_l","br2_r"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br2_l","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"吃饭"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br2_r","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","textAlign":"end"},"content":"¥2,500–¥5,000"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br3","component":"Extended.Row","children":["br3_l","br3_r"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br3_l","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"门票"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"br3_r","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","textAlign":"end"},"content":"¥2,000–¥4,500"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_total","component":"Extended.Column","children":["budget_total_txt"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#F8FAFC","padding":{"top":8,"right":12,"bottom":8,"left":12},"borderWidth":1,"borderColor":"#33000000"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"budget_total_txt","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":2,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"合计：约 ¥6,000–¥11,000 / 天"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tips_card","component":"Extended.Column","children":["tips_body"],"styles":{"width":"matchParent","borderRadius":12,"backgroundColor":"#F7F9FF","padding":{"top":12,"right":12,"bottom":12,"left":12},"borderWidth":1,"borderColor":"#DCE7FF"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tips_body","component":"Extended.Row","children":["tips_dot","tips_txt"],"space":10,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tips_dot","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7"},"content":"●"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"md_travel","components":[{"id":"tips_txt","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":4,"textOverflow":"ellipsis","fontColor":"#99000000","layoutWeight":1},"content":"小贴士：门票尽量线上提前买；避开高峰（07:30–09:30，17:00–19:00）。"}]}}
```
