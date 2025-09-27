# NewAPI Suite 插件部署手册

欢迎使用 NewAPI Suite 插件！本插件是为 [AstrBot](https://github.com/he0119/AstrBot) 设计的一套功能集成套件，旨在打通您的 New API 网站与 QQ 群组之间的桥梁，提供丰富的用户互动与管理功能。

## ✨ 功能特性

*   **用户系统**: 实现 QQ 号与网站用户 ID 的无缝绑定与数据互通。
*   **经济系统**: 内置每日签到、额度查询等功能，提升用户粘性。
*   **娱乐互动**: 提供惊险刺激的 `/打劫` 功能，为群聊增添乐趣。
*   **自动化管理**: 核心功能！能够监控指定群聊，当成员退群时，自动解除其绑定关系并恢复其网站用户组，实现真正的自动化净化。
*   **强大的管理员工具**: 提供远程查询、解绑、调整用户额度等一系列便捷的管理指令。

## 🔧 安装步骤

部署本插件仅需三步，非常简单：

1.  **下载插件**: 从 GitHub 下载本项目，您会得到一个名为 `NewAPI_plugin` 的文件夹。
2.  **放置插件**: 将整个 `NewAPI_plugin` 文件夹移动到您的 AstrBot 实例的 `data/plugins/` 目录下。
3.  **重启服务**: 重启您的 AstrBot 主程序。之后，您应该能在 AstrBot 的 WebUI -> `插件市场` -> `已安装` 列表中看到本插件。

## ⚙️ 核心配置 (重要)

在您使用本插件前，请务必完成以下三个步骤的配置。

### **第一步：配置 `.env` 文件**

本插件的所有机密信息（如数据库密码、API 密钥）都通过 `.env` 文件进行管理，以确保安全。

请在您的 **AstrBot 根目录** (与 `main.py` 或 `run.py` 同级) 创建一个名为 `.env` 的文件，并填入以下内容：

```dotenv
# --- 数据库配置 ---
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_database_user
DB_PASS=your_database_password
DB_NAME=your_database_name

# --- New API 网站配置 ---
# 您的 New API 网站地址，结尾不要带 /
API_BASE_URL=https://your-new-api-domain.com 
# 您在 New API 后台生成的令牌
API_ACCESS_TOKEN=sk-xxxxxxxxxxxxxxxxxxxxxxxx 
# 执行管理员操作时使用的用户ID (通常是 1)
API_ADMIN_USER_ID=1
```

### **第二步：配置数据库**

本插件需要使用一个 **MySQL** 或 **MariaDB** 数据库来存储用户绑定关系和打劫日志。请连接到您的数据库，并执行以下 SQL 语句来创建所需的数据表：

```sql
-- 用户绑定信息表
CREATE TABLE `newapi_bindings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `qq_id` bigint(20) NOT NULL,
  `website_user_id` int(11) NOT NULL,
  `binding_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_check_in_time` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `qq_id` (`qq_id`),
  UNIQUE KEY `website_user_id` (`website_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 每日打劫日志表
CREATE TABLE `daily_heist_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `robber_qq_id` bigint(20) NOT NULL,
  `victim_website_id` int(11) NOT NULL,
  `heist_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `outcome` varchar(10) NOT NULL COMMENT 'SUCCESS, CRITICAL, FAILURE',
  `amount` int(11) NOT NULL COMMENT '涉及的原始 quota 数额',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### **第三步：配置插件 UI**

剩下的所有功能性配置，例如签到奖励额度、打劫成功率、消息模板、监控群号等，都可以在 AstrBot 的 **WebUI 插件界面** 中进行图形化配置，非常方便。

## 📜 指令大全

### **用户指令**

*   `/绑定 [你的网站ID]`
    *   将您的 QQ 与指定的网站用户 ID 进行绑定。
*   `/查询余额`
    *   查询您当前绑定的网站账号剩余额度。
*   `/签到`
    *   进行每日签到，随机获取额度奖励。
*   `/打劫 @目标用户`
    *   对群内另一位已绑定的用户发起打劫！有成有败，后果自负。

### **管理员指令** (需要 AstrBot 管理员权限)

*   `/解绑 [网站ID]`
    *   强制解除指定网站 ID 的绑定关系。
*   `/查询 [网站ID或QQ号]`
    *   智能查询，输入网站 ID 可查到 QQ，输入 QQ 可查到网站 ID。
*   `/调整余额 [网站ID或QQ号] [要增加或减少的额度]`
    *   为指定用户调整额度。例如：`/调整余额 12345 100` 表示增加 100 额度，`/调整余额 12345 -50` 表示减少 50 额度。

## 🤖 自动化功能

### 退群自动净化

这是本插件的核心灵魂功能。您只需在插件的 WebUI 配置中填入需要监控的群号列表。当有成员 **主动退群** 或 **被踢出群聊** 时，插件会自动：
1.  查询该成员是否已绑定网站 ID。
2.  如果已绑定，则自动删除其绑定记录。
3.  同时，通过 API 将其网站用户组恢复为预设的默认组。
4.  在群内发送一条通知，宣告净化仪式完成。

---
Future-404
QQ: 317032529
月亮公益站:733012645
