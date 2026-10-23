"""耳机与音乐入口的共用样例，图片适用统一三行准入。"""



from test_autumn_calendar_photos import expanded

IDENTITY = "photo-ux-violin-stage-square"
VIOLIN = "photo-ux-violin-stage-square"
PATH = "/data/earphone/earphoneBatteryLevel"
ICON = "resources/base/media/icon_music.svg"
ACTION = [{"call": "clickToDeeplink", "args": {
    "intentName": "Music", "bundleName": "", "abilityName": "",
    "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412",
}}]


def earphone_sample():
    task = {"size": "2x2", "userQuery": "耳机状态和收藏歌单", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"earphone": {}}}}
    rows = [
        ["root", "Layout", {"layout": "S-title-content-action"}, ["header", "reading", "cta"]],
        ["header", "SingleLineTitle", {"title": "耳机状态", "icon": ICON}],
        ["reading", "EmphasisText", {"mainText": {"path": PATH}, "secondaryText": "耳机电量"}],
        ["cta", "PillButton", {"label": "收藏歌单", "onClick": ACTION, "icon": ICON}],
        [PATH, "80%"],
    ]
    return expanded(rows, task)


def music_sample(with_icon=True):
    task = {"size": "2x2", "userQuery": "每日推荐和收藏歌单", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {}}}
    rows = [["root", "Layout", {"layout": "S-content-dual-action", "variant": "actions-only"},
             ["daily", "favorite"]]]
    for identity, label in (("daily", "每日推荐"), ("favorite", "收藏歌单")):
        props = {"label": label, "onClick": ACTION}
        if with_icon:
            props["icon"] = ICON
        rows.append([identity, "PillButton", props])
    return expanded(rows, task)
