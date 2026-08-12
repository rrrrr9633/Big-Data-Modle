# 中街冰点 MES 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不影响现有预测性维护系统的前提下，新增一个可通过 Docker 启动、可演示雪糕生产与冻结物料阻断闭环的 Spring Boot + React MES。

**Architecture:** 新应用位于 `mes-icecream/`，以 mes-generator 生成主数据与台账 CRUD；食品领域命令、状态机、追溯和设备采集放在独立 `industry/icecream` 包。MySQL 持久化、React 管理/工位/看板三端共享 REST API；种子数据覆盖报价表中的核心生产、质量、仓储、设备与 11 条线采集点场景。

**Tech Stack:** Java 21、Spring Boot 3、Maven、JPA、Flyway、MySQL 8、React 18、TypeScript、Vite、Docker Compose、Vitest。

---

### Task 1: 建立独立项目与生成器配置

**Files:**
- Create: `mes-icecream/mes-crud.config.json`
- Create: `mes-icecream/apps/mes-api/pom.xml`
- Create: `mes-icecream/apps/mes-web/package.json`
- Create: `mes-icecream/docker-compose.yml`

- [ ] **Step 1: 写入生成器配置**：声明组织、车间、产线、工位、物料、产品、仓库、库位、设备、工装、检验项目、参数阈值、工单、批次、安灯、追溯边等对象。
- [ ] **Step 2: 执行 mes-generator 汇编器**：`node /Users/chenhaoran/.codex/skills/mes-generator/starter/scripts/assemble.mjs --config mes-icecream/mes-crud.config.json --out mes-icecream`，确认源码、迁移、Web feature 分别生成。
- [ ] **Step 3: 建立可编译的 Spring Boot 与 React 宿主**，把生成代码纳入组件扫描和前端路由边界。
- [ ] **Step 4: 运行 `mvn test` 与 `npm run build`，确认骨架可验证。**

### Task 2: 食品领域命令与冻结物料防错（TDD）

**Files:**
- Create: `mes-icecream/apps/mes-api/src/test/java/com/zhongjie/mes/industry/icecream/MaterialGateServiceTest.java`
- Create: `mes-icecream/apps/mes-api/src/main/java/com/zhongjie/mes/industry/icecream/rules/MaterialGateService.java`
- Create: `mes-icecream/apps/mes-api/src/main/java/com/zhongjie/mes/industry/icecream/api/ProductionCommandController.java`

- [ ] **Step 1: 先写失败测试**：冻结奶油批次投料返回 `MATERIAL_LOT_FROZEN` 且工单转为 `BLOCKED`；合格批次投料后返回放行。
- [ ] **Step 2: 运行 `mvn -q -Dtest=MaterialGateServiceTest test`，确认失败原因是缺少实现。**
- [ ] **Step 3: 实现最小的投料校验与状态变迁**：`validateIssue(String lotStatus)` 返回 `GateDecision`，冻结时创建物料安灯事件并列出仓库/品质的下一步。
- [ ] **Step 4: 再次运行测试，确认通过。**

### Task 3: 首件、工艺、回料和 SN 谱系（TDD）

**Files:**
- Create: `mes-icecream/apps/mes-api/src/test/java/com/zhongjie/mes/industry/icecream/IceCreamWorkflowTest.java`
- Create: `mes-icecream/apps/mes-api/src/main/java/com/zhongjie/mes/industry/icecream/workflows/IceCreamWorkflowService.java`
- Create: `mes-icecream/apps/mes-api/src/main/java/com/zhongjie/mes/industry/icecream/traceability/TraceabilityService.java`

- [ ] **Step 1: 写失败测试**：首件未放行不可开工；首件合格后可开工；新 SN 必须携带原料批次、模具、工位、温度参数；回料 SN 与新成品双向关联。
- [ ] **Step 2: 执行指定测试并确认红灯。**
- [ ] **Step 3: 实现 `approveFirstArticle`、`startLine`、`createUnitTrace` 与 `linkRework` 最小行为。**
- [ ] **Step 4: 执行测试并确认绿灯。**

### Task 4: 报价表覆盖的数据投影与接口

**Files:**
- Create: `mes-icecream/apps/mes-api/src/main/java/com/zhongjie/mes/demo/DemoDataService.java`
- Create: `mes-icecream/apps/mes-api/src/main/java/com/zhongjie/mes/demo/DemoController.java`
- Create: `mes-icecream/apps/mes-api/src/test/java/com/zhongjie/mes/demo/DemoDataServiceTest.java`

- [ ] **Step 1: 写失败测试**：演示摘要包含两个指定工单、11 条设备线、298 个采集点、冻结奶油批次与可溯源 SN。
- [ ] **Step 2: 运行测试确认失败。**
- [ ] **Step 3: 实现确定性种子投影和 `/api/v1/demo/summary`、`/api/v1/demo/reset`。**
- [ ] **Step 4: 运行测试确认通过。**

### Task 5: 三端 React 演示界面

**Files:**
- Create: `mes-icecream/apps/mes-web/src/App.tsx`
- Create: `mes-icecream/apps/mes-web/src/features/dashboard/DashboardPage.tsx`
- Create: `mes-icecream/apps/mes-web/src/features/workstation/WorkstationPage.tsx`
- Create: `mes-icecream/apps/mes-web/src/features/traceability/TraceabilityPage.tsx`
- Create: `mes-icecream/apps/mes-web/src/styles.css`

- [ ] **Step 1: 写 Vitest 渲染测试**：冻结工单显示“禁止投料/产线锁止”，正常工单显示完工与 SN 入口。
- [ ] **Step 2: 执行测试确认失败。**
- [ ] **Step 3: 实现看板、PDA 投料校验、SN 追溯页面和加载/错误/阻断状态。**
- [ ] **Step 4: 执行测试、TypeScript 构建确认通过。**

### Task 6: Docker、文档与验收

**Files:**
- Create: `mes-icecream/README.md`
- Create: `mes-icecream/docs/设备物联点位映射.md`
- Create: `mes-icecream/docs/十分钟演示脚本.md`

- [ ] **Step 1: 配置 MySQL、API、Web 容器和本地附件卷。**
- [ ] **Step 2: 为报价表的前处理、凝冻、花色线、包装机点位列出协议/手工上报映射；标明设备模拟器与真实协议边界。**
- [ ] **Step 3: 写入两个工单的重置、冻结阻断、替料恢复和 SN 追溯演示步骤。**
- [ ] **Step 4: 运行 `mvn test`、`npm run build`、`docker compose config`，记录每项输出。**
