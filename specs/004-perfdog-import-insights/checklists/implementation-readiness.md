# Implementation Readiness Checklist: PerfDog 导入与性能洞察报告

**Purpose**: 作为「需求文档自身的单元测试」——核对 spec 是否足够完整、清晰、一致，便于拆 plan/任务；**不**用于验证代码或按钮是否工作。  
**Created**: 2026-03-21  
**Feature**: [spec.md](../spec.md)  
**Context**: 当前无 `plan.md`；`check-prerequisites.ps1` 会提示先跑 `/speckit.plan`。本清单仍以 **spec  alone** 为审查对象。

**本次运行假设**（未单独追问）：

- **范围**：仅 `004-perfdog-import-insights`（`specs/004-perfdog-import-insights/`）  
- **深度**：标准（PR / 实现前评审）  
- **受众**：作者 + 评审者  

---

## Requirement Completeness

- [ ] CHK001 - 是否**逐项**标明 US1～US8 与 FR-001～FR-019 之间的映射关系，避免实现时遗漏 SHOULD 项（如 FR-011）是否进 MVP？ [Completeness, Gap, Spec §User Stories / §FR]

- [ ] CHK002 - FR-013 中「完成本 spec 中 **P1～P4** 能力」是否与 User Story 的 **Priority P1/P2** 或 **US 编号**一致？若指「优先级」或「前四个故事」，是否在 spec 中**消歧**？ [Ambiguity, Consistency, Spec §FR-013]

- [ ] CHK003 - 「**明显异常时段数量**」在 US1 中提及，是否有对应 FR 或 SC 定义「如何计数」或是否仅为展示文案？ [Completeness, Gap, Spec §US1]

- [ ] CHK004 - FR-007 要求建议与现象「**可追溯**」——是否规定**最低交互形式**（链接、锚点、章节编号、仅人工对照）？ [Clarity, Gap, Spec §FR-007]

- [ ] CHK005 - 对比视图中「**基于选定指标的客观对比**」是否在需求层写明**默认排序/默认指标集**，还是完全留给 plan？若留给 plan，是否在 spec 中**显式委托**？ [Clarity, Spec §US5]

---

## Requirement Clarity

- [ ] CHK006 - 「**显著**低帧或长帧」「**异常**升高」等词是否在 spec 或附录中**指向**将在 plan 中给出的量化阈值，避免评审时对验收标准各执一词？ [Clarity, Gap, Spec §FR-004 / §FR-018]

- [ ] CHK007 - 「**异常时段附近**」时间窗口（前后多少秒/多少采样点）是否在需求中**定义或委托**给 plan 并约定可测性？ [Clarity, Gap, Spec §US3 / §FR-005]

- [ ] CHK008 - FR-002 中 FrameInfo 与秒级结论「**若两者时间轴可对齐**」——对齐规则缺失时，需求是否规定**降级文案**（如「帧级与秒级未对齐，仅分别展示」）？ [Completeness, Spec §FR-002]

- [ ] CHK009 - FR-015 中「**可配置阈值**」与「产品默认 3s」——需求是否要求**对外说明**（设置项/配置档）还是仅内部常量？ [Clarity, Gap, Spec §FR-015]

- [ ] CHK010 - 「**等效文件选择**」与 NF-003「文件选择对话框」是否与 FR-001 合并为**同一可测入口集合**（无遗漏、无矛盾）？ [Consistency, Spec §FR-001 / §NF-003]

---

## Requirement Consistency

- [ ] CHK011 - US1「30 秒内」与 SC-001「10 分钟内」、NF-001「2 秒无反馈」——是否在 spec 中说明**各自适用阶段**（如解析 vs 全链路），避免被误读为冲突？ [Consistency, Spec §US1 / §SC-001 / §NF-001]

- [ ] CHK012 - Edge Cases 要求对比流程中拖入第二文件时**明确选择**替换 A/B/取消——是否在 US5 或 FR 中**重复或引用**，保证故事与边界一致？ [Consistency, Spec §Edge Cases / §US5]

- [ ] CHK013 - Out of Scope 中「自动调参」与现有 Toolkit 策略 Tab 的关系，是否在 spec 中**一句话钉死边界**，避免实现时误打通？ [Consistency, Spec §Out of Scope]

- [ ] CHK014 - FR-016「不静默保留巨型缓存」与 FR-014「持久化路径」——是否在需求层澄清**内存缓存 vs 磁盘记忆**的边界？ [Consistency, Spec §FR-014 / §FR-016]

---

## Acceptance Criteria Quality

- [ ] CHK015 - SC-003「尖刺时段」是否与 FR-004/US2 使用**同一可操作定义**（或注明 SC 依赖 plan 中的操作定义）？ [Measurability, Traceability, Spec §SC-003 / §FR-004]

- [ ] CHK016 - SC-004/SC-006 依赖「试用用户」——是否在项目层约定**样本量与招募标准**，否则是否将成功标准改为**可脚本化/走查表**子指标？ [Measurability, Assumption, Spec §SC-004 / §SC-006]

- [ ] CHK017 - SC-009 中「与 @FrameInfo **人工核对一致**」是否明确**抽样方法**（全量/随机/仅异常段），避免验收争议？ [Clarity, Spec §SC-009]

---

## Scenario Coverage

- [ ] CHK018 - **主路径**：从空态 → 导入 → 摘要 → 洞察 → 建议 → 导出，是否在需求中**隐含链完整**且无「仅 FR 无故事」的孤岛？ [Coverage, Spec §US1–US6]

- [ ] CHK019 - **异常路径**：损坏文件、非 Excel、加密工作簿、过大文件——是否均有**对应 Edge Case 或 FR-009/SC-005/SC-008** 覆盖且无重复矛盾？ [Coverage, Spec §Edge Cases / §FR-009]

- [ ] CHK020 - **恢复路径**：解析中途失败、用户清除、对比取消——清除后对比 B 侧、ImportJob 状态是否在需求中**可推断**？ [Coverage, Gap, Spec §US8 / §FR-016]

- [ ] CHK021 - **Toolkit 内切换 Tab**：US7 与「不自动清除」——若应用进程被系统杀死后重启，行为是否在需求中**声明为未定义或等同冷启动**？ [Edge Case, Gap, Spec §US7]

---

## Edge Case Coverage (requirements written?)

- [ ] CHK022 - **汇总行 vs Data_v4** 不一致时，需求是否强制在 **plan 中二选一**并反映到对外报告文案？ [Completeness, Spec §Edge Cases 汇总行]

- [ ] CHK023 - **元数据乱码**时「原始字符串或十六进制摘要」——是否需规定**优先顺序**或并列展示规则？ [Clarity, Spec §Edge Cases 乱码]

- [ ] CHK024 - **.xlsm 宏不执行**——是否在安全/合规需求中与「仅本地、不上传」**并列可追溯**？ [Consistency, Spec §Edge Cases / §Assumptions]

---

## Non-Functional Requirements (as requirements text)

- [ ] CHK025 - NF-002「最大行数/内存上限」仅委托 plan——是否在 spec 中要求 plan **必须产出可引用编号**（便于 SC-008 验收）？ [Traceability, Spec §NF-002 / §SC-008]

- [ ] CHK026 - NF-004 日志是否区分**个人路径脱敏**规则与**错误类型枚举**最小集？ [Completeness, Gap, Spec §NF-004]

- [ ] CHK027 - **离线**（FR-017）是否与 Dependencies 中「未来云扩展」假设**无逻辑冲突**？ [Consistency, Spec §FR-017 / §Assumptions-1]

---

## Dependencies & Assumptions

- [ ] CHK028 - **PerfDog 版本矩阵**（Dependencies）是否要求在 plan/tasks 中落地为**可勾选交付物**（文件名/表格位置）？ [Traceability, Spec §Dependencies]

- [ ] CHK029 - **列名别名映射**（附录 A）是否需在 plan 中规定**维护责任方**（谁在新版 PerfDog 发布后更新映射）？ [Gap, Spec §附录 A]

---

## Ambiguities & Conflicts (explicit review)

- [ ] CHK030 - FR-011 为 SHOULD：是否在 **Scope / 里程碑** 中明确「首期不含对比」时的**对外说明**与 **FR-012 的从属关系**？ [Consistency, Spec §FR-011 / §In Scope]

---

## Notes

- 勾选 `[x]` 表示「需求文档侧已澄清/已补写」，不是表示代码已完成。  
- 解决 CHK002、CHK006、CHK007、CHK015、CHK025 后，再跑 `/speckit.plan` 通常更顺畅。  
- 若需 **UX 专项**需求质量清单，可另建 `checklists/ux.md`（本命令可再次调用并换文件名）。
