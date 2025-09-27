import os
import asyncio
import httpx
import aiomysql
import random  # (确保导入)
from datetime import datetime, timedelta  # (确保导入)
from typing import Optional, Any, Dict, Tuple
from dotenv import load_dotenv, find_dotenv

from astrbot.api import logger, AstrBotConfig

class NewApiCore:
    """
    NewAPI 核心工具类
    """
    def __init__(self, config: AstrBotConfig):
        self.config = config
        self.db_pool: Optional[aiomysql.Pool] = None
        # 初始化时设为None
        self.api_base_url = None
        self.api_access_token = None
        self.api_admin_user_id = "1"
        logger.info("[NewAPI Utils] 核心工具类已实例化，等待异步初始化")

    async def initialize(self) -> bool:
        """异步初始化，从.env加载配置并连接数据库。"""
        logger.info("[NewAPI Utils] 开始异步初始化")
        
        # 加载机密信息
        load_dotenv(find_dotenv())
        self.api_base_url = os.getenv("API_BASE_URL")
        self.api_access_token = os.getenv("API_ACCESS_TOKEN")
        self.api_admin_user_id = os.getenv("API_ADMIN_USER_ID", "1")

        if not self.api_base_url or not self.api_access_token:
            logger.error("[NewAPI Utils] .env 文件中 API 配置不完整")
            # API配置不完整，但继续尝试连接数据库

        # 连接数据库
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASS")
        db_name = os.getenv("DB_NAME")
        
        if not all([db_host, db_port, db_user, db_name]):
            logger.error("[NewAPI Utils] .env 文件中数据库配置不完整")
            return False
            
        try:
            self.db_pool = await aiomysql.create_pool(
                host=db_host, port=int(db_port),
                user=db_user, password=db_pass,
                db=db_name, autocommit=True
            )
            logger.info("[NewAPI Utils] 数据库连接池建立成功。")
            return True
        except Exception as e:
            logger.error(f"[NewAPI Utils] 数据库初始化失败: {e}", exc_info=True)
            self.db_pool = None
            return False

    async def execute_query(self, query: str, args: Optional[Tuple] = None, fetch: Optional[str] = None) -> Any:
        if self.db_pool is None:
            logger.error("[NewAPI Utils] 数据库未连接，无法查询。")
            return None
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor if fetch else aiomysql.Cursor) as cur:
                await cur.execute(query, args)
                if fetch == 'one':
                    result = await cur.fetchone()
                    return result
                elif fetch == 'all':
                    result = await cur.fetchall()
                    return result
                result = cur.rowcount
                return result

    async def api_request(self, method: str, endpoint: str, json_data: Optional[Dict] = None) -> Optional[Dict]:
        # 使用self中保存的配置
        if not self.api_base_url or not self.api_access_token:
            logger.error("[NewAPI Utils] API 配置未加载，请求中止。")
            return None
        
        url = f"{self.api_base_url}{endpoint}"
        headers = { "Authorization": self.api_access_token, "New-Api-User": self.api_admin_user_id }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, headers=headers, json=json_data, timeout=10.0)
                response.raise_for_status()
                result = response.json()
                return result
        except Exception as e:
            logger.error(f"[NewAPI Utils] API 请求异常: {e}", exc_info=True)
            return None

    # --- 高级辅助方法 ---
    async def get_user_by_qq(self, qq_id: int) -> Optional[Dict]: return await self.execute_query("SELECT * FROM newapi_bindings WHERE qq_id = %s", (qq_id,), fetch='one')

    async def get_user_by_website_id(self, website_user_id: int) -> Optional[Dict]: return await self.execute_query("SELECT * FROM newapi_bindings WHERE website_user_id = %s", (website_user_id,), fetch='one')
    async def get_api_user_data(self, user_id: int) -> Optional[Dict]:
        response = await self.api_request("GET", f"/api/user/{user_id}")
        if response and response.get("success"): return response.get("data")
        return None
    async def update_api_user(self, user_profile: Dict) -> bool:
        response = await self.api_request("PUT", "/api/user/", json_data=user_profile)
        return response and response.get("success", False)
    async def insert_binding(self, qq_id: int, website_user_id: int) -> int: return await self.execute_query("INSERT INTO newapi_bindings (qq_id, website_user_id) VALUES (%s, %s)", (qq_id, website_user_id))
    async def delete_binding(self, *, qq_id: Optional[int] = None, website_user_id: Optional[int] = None) -> int:
        if qq_id: return await self.execute_query("DELETE FROM newapi_bindings WHERE qq_id = %s", (qq_id,))
        elif website_user_id: return await self.execute_query("DELETE FROM newapi_bindings WHERE website_user_id = %s", (website_user_id,))
        return 0

    async def set_check_in_time(self, qq_id: int) -> int:
        """更新指定QQ用户的最后签到时间为当前。"""
        query = "UPDATE newapi_bindings SET last_check_in_time = %s WHERE qq_id = %s"
        return await self.execute_query(query, (datetime.utcnow(), qq_id))

    async def revert_user_group(self, website_user_id: int) -> bool:
        """将指定网站用户恢复至退群后的默认用户组。"""
        api_user_data = await self.get_api_user_data(website_user_id)
        if not api_user_data:
            logger.warning(f"无法获取网站ID {website_user_id} 的用户数据，跳过用户组恢复操作。")
            return False


        leave_conf = self.config.get('group_leave_settings', {})
        revert_group = leave_conf.get('revert_group_on_leave', 'default')
        
        # 仅在用户组不一致时更新，避免不必要的API请求
        if api_user_data.get('group') != revert_group:
            api_user_data['group'] = revert_group
            update_success = await self.update_api_user(api_user_data)
            if update_success:
                logger.info(f"成功将网站用户 {website_user_id} 恢复至用户组: {revert_group}")
            else:
                logger.error(f"恢复网站用户 {website_user_id} 至用户组 {revert_group} 失败。")
            return update_success
        
        logger.info(f"网站用户 {website_user_id} 已在目标恢复组 {revert_group} 中，无需操作。")
        return True

    async def perform_check_in(self, qq_id: int, binding: Optional[Dict] = None) -> Tuple[str, Dict[str, Any]]:
        """
        执行完整的签到逻辑，返回一个元组 (状态码, 详情字典)。
        """
        check_in_conf = self.config.get('check_in_settings', {})
        if not check_in_conf.get('enabled', False):
            return "DISABLED", {}

        # 如果未传入binding对象，则在此查询
        if not binding:
            binding = await self.get_user_by_qq(qq_id)
        
        if not binding:
            return "NOT_BOUND", {}

        # 1. 判断今日是否已签到 (适配时区)
        offset_hours = check_in_conf.get('timezone_offset_hours', 0)
        time_delta = timedelta(hours=offset_hours)
        local_today = (datetime.utcnow() + time_delta).date()
        
        last_check_in_time = binding.get('last_check_in_time')
        is_first_check_in = last_check_in_time is None

        if not is_first_check_in:
            local_last_check_in_date = (last_check_in_time + time_delta).date()
            if local_last_check_in_date == local_today:
                return "ALREADY_CHECKED_IN", {}

        # 2. 计算额度
        ratio = self.config.get('binding_settings.quota_display_ratio', 500000)
        bonus_quota = 0
        is_doubled = False
        if is_first_check_in and check_in_conf.get('first_check_in_bonus_enabled', False):
            bonus_display_quota = check_in_conf.get('first_check_in_bonus_display_quota', 0)
            bonus_quota = int(bonus_display_quota * ratio)
        else:
            is_doubled = random.random() < check_in_conf.get('double_chance', 0.0)

        min_display_q = check_in_conf.get('min_display_quota', 0)
        max_display_q = check_in_conf.get('max_display_quota', 0)
        base_display_quota = random.uniform(min_display_q, max_display_q)
        base_quota = int(base_display_quota * ratio)
        
        regular_quota = base_quota * 2 if is_doubled else base_quota
        final_quota = regular_quota + bonus_quota

        # 3. 更新API数据
        website_user_id = binding['website_user_id']
        api_user_data = await self.get_api_user_data(website_user_id)
        if not api_user_data:
            return "API_USER_NOT_FOUND", {}

        current_quota = api_user_data.get("quota", 0)
        api_user_data["quota"] = current_quota + final_quota
        
        if not await self.update_api_user(api_user_data):
            return "API_UPDATE_FAILED", {}
            
        # 4. 更新数据库签到时间并返回结果
        await self.set_check_in_time(qq_id)
        
        display_added = final_quota / ratio
        display_total = (current_quota + final_quota) / ratio

        return "SUCCESS", {
            "is_first": is_first_check_in,
            "is_doubled": is_doubled,
            "display_added": display_added,
            "display_total": display_total,
            "user_qq": qq_id,  # (新增)
            "site_id": website_user_id  # (新增)
        }

    async def purge_user_binding(self, website_user_id: int) -> Tuple[bool, Optional[Dict]]:
        """
        一键解绑用户，自动恢复用户组并删除绑定记录。返回 (操作是否成功, 被解绑者的绑定信息)。
        """
        # 1. 查找用户是否存在
        binding_info = await self.get_user_by_website_id(website_user_id)
        if not binding_info:
            logger.warning(f"净化请求失败：未找到网站ID {website_user_id} 的绑定记录。")
            return False, None

        try:
            # 2. 恢复用户组 -> 删除绑定记录
            logger.info(f"开始净化网站ID {website_user_id} (QQ: {binding_info['qq_id']})...")
            
            await self.revert_user_group(website_user_id)
            rows_affected = await self.delete_binding(website_user_id=website_user_id)
            
            if rows_affected > 0:
                logger.info(f"净化成功：已删除网站ID {website_user_id} 的绑定记录。")
                return True, binding_info
            else:
                # 处理理论上不应发生的小概率事件
                logger.error(f"净化异常：记录存在但删除失败，数据库影响行数为0。")
                return False, binding_info

        except Exception as e:
            logger.error(f"执行净化网站ID {website_user_id} 的过程中发生未知错误: {e}", exc_info=True)
            return False, binding_info

    async def lookup_binding(self, identifier: int) -> Tuple[str, Optional[Dict]]:
        """
        智能查询绑定关系，自动判断 identifier 是网站ID还是QQ号。返回 (标识符类型, 绑定信息字典)。
        """
        # 尝试作为网站ID查询
        binding = await self.get_user_by_website_id(identifier)
        if binding:
            return "WEBSITE_ID", binding

        # 尝试作为QQ号查询
        binding = await self.get_user_by_qq(identifier)
        if binding:
            return "QQ_ID", binding

        # 查询失败
        return "NOT_FOUND", None

    async def adjust_balance_by_identifier(
        self, identifier: int, display_adjustment: float
    ) -> Tuple[str, Optional[Dict]]:
        """
        智能识别并调整用户余额。返回 (状态码, 详情字典)。
        """
        # 1. 锁定目标
        id_type, binding = await self.lookup_binding(identifier)
        if id_type == "NOT_FOUND":
            return "USER_NOT_FOUND", None

        website_user_id = binding['website_user_id']

        # 2. 计算
        api_user_data = await self.get_api_user_data(website_user_id)
        if not api_user_data:
            return "API_FETCH_FAILED", {"website_user_id": website_user_id}

        ratio = self.config.get('binding_settings.quota_display_ratio', 500000)
        raw_quota_adjustment = int(display_adjustment * ratio)
        
        current_raw_quota = api_user_data.get("quota", 0)
        new_total_raw_quota = current_raw_quota + raw_quota_adjustment

        # 3. 安全检查，防止额度为负
        if new_total_raw_quota < 0:
            new_total_raw_quota = 0
            logger.warning(f"为用户 {website_user_id} 调整余额后会导致负数，已自动修正为 0。")

        # 4. 更新API数据
        api_user_data["quota"] = new_total_raw_quota
        
        if not await self.update_api_user(api_user_data):
            return "API_UPDATE_FAILED", {"website_user_id": website_user_id}
            
        # 5. 返回结果
        new_display_quota = new_total_raw_quota / ratio
        return "SUCCESS", {
            "website_user_id": website_user_id,
            "new_display_quota": new_display_quota
        }

    async def get_today_heist_counts_by_qq(self, robber_qq_id: int) -> int:
        """查询指定QQ今天主动打劫次数。"""
        # 注意：CURDATE() 依赖数据库服务器的当前日期设置。
        query = "SELECT COUNT(*) as count FROM daily_heist_log WHERE robber_qq_id = %s AND DATE(heist_time) = CURDATE()"
        result = await self.execute_query(query, (robber_qq_id,), fetch='one')
        return result['count'] if result else 0

    async def get_today_defenses_count_by_id(self, victim_website_id: int) -> int:
        """查询指定网站ID今天被成功打劫次数。"""
        query = "SELECT COUNT(*) as count FROM daily_heist_log WHERE victim_website_id = %s AND DATE(heist_time) = CURDATE() AND outcome IN ('SUCCESS', 'CRITICAL')"
        result = await self.execute_query(query, (victim_website_id,), fetch='one')
        return result['count'] if result else 0

    async def log_heist_attempt(self, robber_qq_id: int, victim_website_id: int, outcome: str, amount: int) -> int:
        """记录一次完整的打劫事件。"""
        query = """
            INSERT INTO daily_heist_log 
            (robber_qq_id, victim_website_id, heist_time, outcome, amount) 
            VALUES (%s, %s, %s, %s, %s)
        """
        # 使用UTC时间以保持数据一致性
        return await self.execute_query(query, (robber_qq_id, victim_website_id, datetime.utcnow(), outcome, amount))

    async def transfer_display_quota(
        self, from_user_id: int, to_user_id: int, display_amount: float, allow_partial: bool = False
    ) -> Tuple[bool, float, int]:
        """
        根据显示额度安全地划转资金，返回 (是否成功, 实际划转的显示额度, 实际划转的原始数额)。
        """
        ratio = self.config.get('binding_settings.quota_display_ratio', 500000)
        raw_amount = int(display_amount * ratio)

        transfer_success, actual_raw_amount = await self._transfer_quota(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            raw_amount=raw_amount,
            allow_partial=allow_partial
        )

        actual_display_amount = actual_raw_amount / ratio
        
        return transfer_success, actual_display_amount, actual_raw_amount

    async def _transfer_quota(
        self, from_user_id: int, to_user_id: int, raw_amount: int, allow_partial: bool = False
    ) -> Tuple[bool, int]:
        """处理双向余额划转，确保事务安全。"""
        from_user = await self.get_api_user_data(from_user_id)
        to_user = await self.get_api_user_data(to_user_id)

        if not from_user or not to_user:
            return False, 0

        from_balance = from_user.get("quota", 0)
        
        actual_amount = raw_amount
        if from_balance < raw_amount:
            if allow_partial:
                actual_amount = from_balance
            else:
                return False, 0

        if actual_amount <= 0:
            return True, 0

        from_user["quota"] -= actual_amount
        update_from_success = await self.update_api_user(from_user)

        if not update_from_success:
            return False, 0

        to_user["quota"] += actual_amount
        update_to_success = await self.update_api_user(to_user)

        if not update_to_success:
            logger.error(f"Quota transfer failed at receiving end (to_user_id: {to_user_id}). Attempting to roll back deduction for from_user_id: {from_user_id}.")
            
            # 回滚
            from_user["quota"] += actual_amount
            rollback_update_success = await self.update_api_user(from_user)
            
            if not rollback_update_success:
                logger.critical(f"CRITICAL FAILURE: Rollback for from_user_id {from_user_id} FAILED. User has lost {actual_amount} quota. Manual intervention required.")
            
            return False, 0
        
        return True, actual_amount