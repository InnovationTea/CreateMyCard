映射规则：

{"id", "type", {...props...}, [...children...]}

{"version":"v0.9","updateComponents":{"surfaceId":"weather_card","components":[{"id":"xxx","component":"xxx","children":[...children...],...props...,"styles":{...props...}}}]}}

{"version":"v0.9","updateComponents":{"surfaceId":"weather_card",

前面这种直接封装现成的，都是固定写法

举例：

compact协议：
{"body", "Column", {"width":"matchParent","alignItems":"stretch","space":16,}, ["current","divider1","forecast"]}

a2ui协议：
{"version":"v0.9","updateComponents":{"surfaceId":"weather_card","components":[{"id":"body","component":"Extended.Column","children":["current","divider1","forecast"],"space":16,"styles":{"width":"matchParent","alignItems":"stretch"}}}]}}

最前面的"body"就对应"id":"body"
第二项"Column"就对应"component":"Extended.Column"，
第三项{"width":"matchParent","alignItems":"stretch","space":16,}就对应"space":16,"styles":{"width":"matchParent","alignItems":"stretch"}
第四项["current","divider1","forecast"]就对应"children":["current","divider1","forecast"]

注意:a2ui协议中的样式可能有多种，例如，"space":16,"styles":{"width":"matchParent","alignItems":"stretch"}}}]} 一些是被styles包裹的，还有例如space是没有被styles包裹的，这些都是根据协议规定（有些在styles里面、有些是单独的）来的，@genui-sdk/prompt/src/prompt-assets/ui_schema.ts ，直接根据需求映射即可。