# locations.json 字段说明（PRD 6.1 节）

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | string | 是 | 唯一标识 |
| name | string | 是 | 地点名称 |
| region | string | 是 | 所属城市/区域（如「上海周边」「杭州周边」） |
| latitude | float | 是 | 纬度 |
| longitude | float | 是 | 经度 |
| bortle | int (1-9) | 是 | Bortle 光污染等级，数值越低越暗 |
| access_modes | string[] | 是 | 可达交通方式，如 ["自驾", "公共交通"]。若仅含 "自驾"，Agent 2 会过滤无车用户 |
| access_notes | string | 否 | 交通补充说明（如「末班公交 21:00」） |
| terrain_notes | string | 否 | 地形说明（如「东侧有山脊遮挡」） |
| facilities | string | 否 | 设施说明（如「有停车场」「无厕所」） |
| source | string | 否 | 信息来源（如「小红书用户推荐」「实地验证」） |
