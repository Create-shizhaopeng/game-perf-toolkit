## ADDED Requirements

### Requirement: 配置工作台统一文档上下文

工作台 SHALL 在单一文档上下文中同时提供编辑与对比：用户加载一份 `gameperfconfig.xml` 后，无需离开工作台即可完成编辑、对比、采纳与推送，MUST NOT 要求"对比采纳 → 另存为 → 重新加载"的中间链路。

#### Scenario: 从设备加载并编辑
- **WHEN** 用户打开配置工作台且设备已连接
- **THEN** 自动拉取设备 `/system/etc/gameperfconfig.xml` 作为当前编辑文档，顶栏显示来源为「设备」

#### Scenario: 对比采纳后编辑视图立即反映
- **WHEN** 用户在对比视图采纳一项差异后切回编辑视图
- **THEN** 编辑视图显示已采纳的最新内容，且未保存指示生效

### Requirement: 游戏选择与模式垂直卡片平铺

工作台 SHALL 允许用户选择单个游戏，并将该游戏的所有性能模式以垂直卡片形式同时平铺展示；每张模式卡片默认展开、可独立折叠。

#### Scenario: 选中游戏展示全部模式
- **WHEN** 用户在游戏下拉中选择某游戏
- **THEN** 该游戏的所有 Mode（如 Normal / HighPerf）各自以垂直卡片罗列，全部同时可见，MUST NOT 依赖模式下拉切换

#### Scenario: 折叠低关注模式
- **WHEN** 用户点击某模式卡片头部的折叠按钮
- **THEN** 该卡片仅保留头部行，其余模式卡片不受影响

### Requirement: 频率档位双下拉编辑

温度档位表每行的每组频率（Gold / Prime / Gpu）SHALL 以「下限 + 上限」两个下拉框编辑，选项显示 Hz 语义值；MUST 移除手输 `a_b` 下标串的编辑方式；MUST 保留下标↔Hz 的自动换算。

#### Scenario: 用下拉选择频率范围
- **WHEN** 用户在 Gold 下限下拉选择 710MHz、上限下拉选择 1.8GHz
- **THEN** 两个下拉显示所选值，对应 XML `<item name="Gold">` 写入正确的下标对，MUST NOT 要求用户手输下标

#### Scenario: 窄窗口横向滚动
- **WHEN** 编辑区可用宽度不足以容纳整张频率表
- **THEN** 频率表区域出现横向滚动条，两个下拉框始终完整显示、文字不截断

### Requirement: BindCore 二进制输入与十六进制回显

BindCore 绑核 mask SHALL 以二进制形式输入，并实时回显对应的十六进制值（XML 实际存储形式）；输入校验就地反馈。

#### Scenario: 输入二进制回显十六进制
- **WHEN** 用户在绑核输入框输入 `00111100`
- **THEN** 相邻回显区显示 `3c`

#### Scenario: 非法输入就地提示
- **WHEN** 用户输入含非 0/1 字符
- **THEN** 输入框就地标红提示，MUST NOT 将非法值写入 XML

### Requirement: 策略表单层级路径展示

策略区表单 SHALL 为每个可编辑字段展示包含父级路径的完整语义层级，使嵌套同名节点可区分；SHALL 覆盖 Game 与 Mode 下所有属性与叶子文本节点，MUST NOT 因层级路径缺失导致字段不可见或不可编辑。

#### Scenario: 区分嵌套同名节点
- **WHEN** 某策略块包含多个同名子节点（如多个 `item` 或 `tid`）
- **THEN** 各字段 key 显示含父级路径的完整路径（如 `Touch/item[1]/fps`），用户可区分并分别编辑

#### Scenario: 全部标签可编辑
- **WHEN** 用户在策略区浏览某游戏某模式的全部策略块
- **THEN** 每个可定位的属性和叶子文本均有对应编辑控件

### Requirement: 补齐编辑盲区

工作台 SHALL 支持编辑 `PreEnv`（CPU / GPU 频率表）与根节点 `version`；`PreEnv` 通过模式卡片内「高级…」入口访问。

#### Scenario: 编辑 PreEnv 频率表
- **WHEN** 用户在某模式卡片点击「高级…」入口
- **THEN** 打开 PreEnv 频率表编辑区，可增删改 CPU/GPU 频点，保存后写回 XML 并同步所有频率下拉的选项

#### Scenario: 编辑根 version
- **WHEN** 用户在顶栏修改 version 值
- **THEN** 写回 XML 根节点 `version` 属性

### Requirement: 未保存指示与撤销重做

工作台 SHALL 在文档存在未保存修改时于顶栏显示指示；SHALL 提供撤销与重做，覆盖频率、温度、策略、BindCore 等编辑操作。

#### Scenario: 未保存指示
- **WHEN** 用户完成任意一次编辑后
- **THEN** 顶栏显示「未保存」指示，直至文档被保存或重新加载

#### Scenario: 撤销单步编辑
- **WHEN** 用户触发撤销最近一次编辑
- **THEN** 该编辑被回退，XML 与界面同步刷新

### Requirement: 策略区局部刷新保焦点

策略区编辑 SHALL 采用局部更新，MUST NOT 在单字段编辑后整块重建导致焦点或滚动位置丢失。

#### Scenario: 编辑字段不丢焦点
- **WHEN** 用户在策略表单某字段修改值并确认
- **THEN** 仅该字段更新，焦点与滚动位置保持不变
