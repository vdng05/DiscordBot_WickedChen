"""
Async SQLite Database Manager using aiosqlite with WAL mode
"""

import asyncio
import aiosqlite
from contextlib import asynccontextmanager
import json
from pathlib import Path
import time
from typing import Optional, Dict, List, Any
from utils.logger import setup_logging
from utils.constants import DEFAULT_WEEKLY_QUESTS, DEFAULT_DAILY_QUESTS, LEVELS, PET_SPECIES, get_pet_level_info

logger = setup_logging("Database")

class DatabaseManager:
    """Quản lý kết nối SQLite bất đồng bộ và thực thi truy vấn"""

    @asynccontextmanager
    async def connect(self):
        """Tạo kết nối SQLite bất đồng bộ với timeout 30s và cấu hình tối ưu chống lock"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA busy_timeout = 30000;")
            yield db

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._log_dispatcher = None

    def set_log_dispatcher(self, dispatcher):
        """Đăng ký callback tự động gửi nhật ký ra kênh Discord riêng của từng băng."""
        self._log_dispatcher = dispatcher

    async def initialize(self):
        """Khởi tạo file cơ sở dữ liệu, kích hoạt WAL mode và chạy migrations"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.connect() as db:
            # Kích hoạt WAL Mode & Foreign Keys
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")

            schema = """
            -- 1. Cấu hình riêng cho từng Discord Server
            CREATE TABLE IF NOT EXISTS guild_configs (
                guild_id TEXT PRIMARY KEY,
                clan_category_id TEXT NOT NULL,
                log_channel_id TEXT,
                allow_member_create INTEGER DEFAULT 1,
                required_role_id TEXT,
                leave_cooldown_hours INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL
            );

            -- 2. Thông tin chính của từng băng đảng
            CREATE TABLE IF NOT EXISTS clans (
                clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                name TEXT NOT NULL,
                tag TEXT NOT NULL,
                description TEXT DEFAULT 'Chưa có khẩu hiệu.',
                role_id TEXT NOT NULL UNIQUE,
                text_channel_id TEXT NOT NULL UNIQUE,
                log_channel_id TEXT,
                voice_channel_id TEXT NOT NULL UNIQUE,
                extra_voice_channel_id TEXT,
                leader_id TEXT NOT NULL,
                join_mode TEXT DEFAULT 'APPROVAL' CHECK (join_mode IN ('OPEN', 'APPROVAL', 'INVITE_ONLY')),
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                weekly_exp INTEGER DEFAULT 0,
                max_members INTEGER DEFAULT 15,
                color_hex TEXT DEFAULT '#5865F2',
                secondary_color_hex TEXT,
                logo_url TEXT,
                banner_url TEXT,
                last_renamed_at INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                UNIQUE(guild_id, name),
                UNIQUE(guild_id, tag),
                FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
            );

            -- 3. Thành viên trong băng
            CREATE TABLE IF NOT EXISTS clan_members (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                clan_id INTEGER NOT NULL,
                rank TEXT NOT NULL DEFAULT 'MEMBER' CHECK (rank IN ('LEADER', 'CO_LEADER', 'OFFICER', 'MEMBER')),
                contribution_points INTEGER DEFAULT 0,
                checkin_streak INTEGER DEFAULT 0,
                last_checkin_date TEXT,
                joined_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 3b. Lịch sử điểm danh độc lập theo user (chống thoát/vào băng để farm điểm danh trong ngày)
            CREATE TABLE IF NOT EXISTS member_checkin_history (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                last_checkin_date TEXT NOT NULL,
                checkin_streak INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, user_id)
            );

            -- 4. Theo dõi cooldown sau khi rời băng
            CREATE TABLE IF NOT EXISTS member_cooldowns (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );

            -- 5. Lời mời & Đơn xin gia nhập
            CREATE TABLE IF NOT EXISTS clan_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                request_type TEXT NOT NULL CHECK (request_type IN ('INVITE', 'APPLY')),
                note TEXT,
                status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED')),
                message_id TEXT,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 6. Kèo chơi game / Party nội bộ
            CREATE TABLE IF NOT EXISTS clan_parties (
                party_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                creator_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                title TEXT NOT NULL,
                max_slots INTEGER NOT NULL,
                scheduled_at INTEGER,
                reminded INTEGER DEFAULT 0,
                status TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
                created_at INTEGER NOT NULL,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS clan_party_participants (
                party_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                slot_type TEXT NOT NULL CHECK (slot_type IN ('MAIN', 'RESERVE')),
                joined_at INTEGER NOT NULL,
                PRIMARY KEY (party_id, user_id),
                FOREIGN KEY (party_id) REFERENCES clan_parties(party_id) ON DELETE CASCADE
            );

            -- 7. Nhiệm vụ tuần đồng đội
            CREATE TABLE IF NOT EXISTS clan_weekly_quests (
                quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                week_key TEXT NOT NULL,
                quest_type TEXT NOT NULL CHECK (quest_type IN ('CHECKIN_COUNT', 'VOICE_MINUTES', 'CHAT_MESSAGES', 'PARTY_COMPLETED')),
                target_value INTEGER NOT NULL,
                current_value INTEGER DEFAULT 0,
                reward_exp INTEGER NOT NULL,
                completed INTEGER DEFAULT 0,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 8. Nhật ký hoạt động băng
            CREATE TABLE IF NOT EXISTS clan_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                actor_id TEXT NOT NULL,
                target_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 7. Cột mốc lịch sử & Kỷ niệm của băng
            CREATE TABLE IF NOT EXISTS clan_milestones (
                milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                achieved_at INTEGER NOT NULL,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 8. Phân quyền Role sử dụng Bot (Dành cho Chủ Bot)
            CREATE TABLE IF NOT EXISTS bot_access_configs (
                guild_id TEXT PRIMARY KEY,
                access_mode TEXT NOT NULL DEFAULT 'ALL' CHECK (access_mode IN ('ALL', 'ROLES', 'NONE')),
                allowed_role_ids TEXT NOT NULL DEFAULT '[]',
                updated_at INTEGER NOT NULL
            );

            -- 9. Nhiệm vụ ngày của băng
            CREATE TABLE IF NOT EXISTS clan_daily_quests (
                quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                date_key TEXT NOT NULL,
                quest_type TEXT NOT NULL,
                target_value INTEGER NOT NULL,
                current_value INTEGER DEFAULT 0,
                reward_exp INTEGER NOT NULL,
                reward_coins INTEGER DEFAULT 30,
                completed INTEGER DEFAULT 0,
                UNIQUE(clan_id, date_key, quest_type),
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 10. Linh Thú Băng Đảng (Clan Pet)
            CREATE TABLE IF NOT EXISTS clan_pets (
                clan_id INTEGER PRIMARY KEY,
                species TEXT NOT NULL,
                name TEXT NOT NULL,
                exp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                stage INTEGER DEFAULT 1,
                hunger INTEGER DEFAULT 80,
                mood INTEGER DEFAULT 80,
                pet_coins INTEGER DEFAULT 100,
                equipped_json TEXT NOT NULL DEFAULT '{}',
                allow_member_style INTEGER DEFAULT 0,
                last_decay_at INTEGER NOT NULL,
                daily_exp_date TEXT,
                daily_exp_earned INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 11. Tủ đồ chung của Linh Thú Băng
            CREATE TABLE IF NOT EXISTS clan_pet_inventory (
                clan_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                purchased_at INTEGER NOT NULL,
                PRIMARY KEY (clan_id, item_id),
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            );

            -- 12. Cooldown tương tác Linh Thú theo từng thành viên
            CREATE TABLE IF NOT EXISTS clan_pet_cooldowns (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                last_used_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id, action_type)
            );

            -- Các chỉ mục tối ưu hiệu năng
            CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id);
            CREATE INDEX IF NOT EXISTS idx_clan_logs_clan_time ON clan_logs(clan_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_clan_requests_status ON clan_requests(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_clan_parties_reminder ON clan_parties(status, reminded, scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_weekly_quests_clan_week ON clan_weekly_quests(clan_id, week_key);
            CREATE INDEX IF NOT EXISTS idx_clan_milestones_clan ON clan_milestones(clan_id, achieved_at DESC);
            """

            await db.executescript(schema)
            await db.commit()

            # Migration: thêm secondary_color_hex, log_channel_id và last_global_challenge_at nếu chưa có
            for alter_sql in (
                "ALTER TABLE clans ADD COLUMN secondary_color_hex TEXT",
                "ALTER TABLE clans ADD COLUMN log_channel_id TEXT",
                "ALTER TABLE clans ADD COLUMN last_global_challenge_at INTEGER DEFAULT 0",
            ):
                try:
                    await db.execute(alter_sql)
                    await db.commit()
                except Exception:
                    pass

            # Migration: thêm custom_title cho clan_members nếu chưa có
            try:
                await db.execute("ALTER TABLE clan_members ADD COLUMN custom_title TEXT")
                await db.commit()
            except Exception:
                pass

            # Migration: nâng cấp CHECK constraint cho clan_weekly_quests hỗ trợ CHAT_MESSAGES
            try:
                async with db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='clan_weekly_quests'") as cur:
                    tbl_row = await cur.fetchone()
                    if tbl_row and "CHAT_MESSAGES" not in tbl_row[0]:
                        await db.execute("""
                            CREATE TABLE IF NOT EXISTS clan_weekly_quests_new (
                                quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                clan_id INTEGER NOT NULL,
                                week_key TEXT NOT NULL,
                                quest_type TEXT NOT NULL CHECK (quest_type IN ('CHECKIN_COUNT', 'VOICE_MINUTES', 'CHAT_MESSAGES', 'PARTY_COMPLETED')),
                                target_value INTEGER NOT NULL,
                                current_value INTEGER DEFAULT 0,
                                reward_exp INTEGER NOT NULL,
                                completed INTEGER DEFAULT 0,
                                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
                            )
                        """)
                        await db.execute("INSERT OR IGNORE INTO clan_weekly_quests_new SELECT * FROM clan_weekly_quests")
                        await db.execute("DROP TABLE clan_weekly_quests")
                        await db.execute("ALTER TABLE clan_weekly_quests_new RENAME TO clan_weekly_quests")
                        await db.execute("CREATE INDEX IF NOT EXISTS idx_weekly_quests_clan_week ON clan_weekly_quests(clan_id, week_key)")
                        await db.commit()
            except Exception as mig_err:
                logger.warning(f"Lỗi kiểm tra migration weekly quests: {mig_err}")

            # Xóa các cooldown cũ còn tồn đọng để bỏ hẳn time out rời băng theo yêu cầu
            try:
                await db.execute("DELETE FROM member_cooldowns")
                await db.commit()
            except Exception:
                pass

        logger.info(f"Đã kết nối và khởi tạo schema SQLite (WAL Mode) tại: {self.db_path}")

    # =========================================================================
    # GUILD CONFIGS
    # =========================================================================
    async def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM guild_configs WHERE guild_id = ?", (str(guild_id),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def save_guild_config(self, guild_id: int, category_id: int, log_channel_id: Optional[int],
                                allow_member_create: bool, required_role_id: Optional[int], cooldown_hours: int = 24):
        now = int(time.time())
        sql = """
        INSERT INTO guild_configs (
            guild_id, clan_category_id, log_channel_id, allow_member_create, required_role_id, leave_cooldown_hours, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            clan_category_id = excluded.clan_category_id,
            log_channel_id = excluded.log_channel_id,
            allow_member_create = excluded.allow_member_create,
            required_role_id = excluded.required_role_id,
            leave_cooldown_hours = excluded.leave_cooldown_hours
        """
        async with self.connect() as db:
            await db.execute(sql, (
                str(guild_id),
                str(category_id),
                str(log_channel_id) if log_channel_id else None,
                1 if allow_member_create else 0,
                str(required_role_id) if required_role_id else None,
                cooldown_hours,
                now
            ))
            await db.commit()

    async def get_bot_access_config(self, guild_id: int) -> Dict[str, Any]:
        """Lấy cấu hình Role được phép sử dụng bot trong server (mặc định: ALL)."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM bot_access_configs WHERE guild_id = ?", (str(guild_id),)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"mode": "ALL", "role_ids": []}
                try:
                    role_ids = json.loads(row["allowed_role_ids"] or "[]")
                except Exception:
                    role_ids = []
                return {"mode": row["access_mode"], "role_ids": [str(r) for r in role_ids]}

    async def set_bot_access_config(self, guild_id: int, mode: str, role_ids: Optional[List[str]] = None) -> None:
        """Cập nhật cấu hình phân quyền sử dụng bot (ALL, ROLES, NONE)."""
        now = int(time.time())
        clean_mode = mode if mode in ("ALL", "ROLES", "NONE") else "ALL"
        serialized_roles = json.dumps([str(r) for r in (role_ids or [])])
        sql = """
        INSERT INTO bot_access_configs (guild_id, access_mode, allowed_role_ids, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            access_mode = excluded.access_mode,
            allowed_role_ids = excluded.allowed_role_ids,
            updated_at = excluded.updated_at
        """
        async with self.connect() as db:
            await db.execute(sql, (str(guild_id), clean_mode, serialized_roles, now))
            await db.commit()

    # =========================================================================
    # CLANS CRUD
    # =========================================================================
    async def create_clan(self, guild_id: int, name: str, tag: str, description: str,
                          role_id: int, text_channel_id: int, voice_channel_id: int,
                          leader_id: int, color_hex: str = "#5865F2",
                          log_channel_id: Optional[int] = None) -> int:
        now = int(time.time())
        sql = """
        INSERT INTO clans (
            guild_id, name, tag, description, role_id, text_channel_id, log_channel_id, voice_channel_id, leader_id, color_hex, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with self.connect() as db:
            cursor = await db.execute(sql, (
                str(guild_id), name, tag, description, str(role_id),
                str(text_channel_id), str(log_channel_id) if log_channel_id else None,
                str(voice_channel_id), str(leader_id), color_hex, now
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_clan_by_id(self, clan_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE clan_id = ?", (clan_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_name(self, guild_id: int, name: str) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE guild_id = ? AND LOWER(name) = LOWER(?)", (str(guild_id), name.strip())) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_tag(self, guild_id: int, tag: str) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE guild_id = ? AND LOWER(tag) = LOWER(?)", (str(guild_id), tag.strip())) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_role_id(self, role_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE role_id = ?", (str(role_id),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_channel_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM clans WHERE text_channel_id = ? OR log_channel_id = ? OR voice_channel_id = ? OR extra_voice_channel_id = ?"
            async with db.execute(query, (str(channel_id), str(channel_id), str(channel_id), str(channel_id))) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_member(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT c.*, m.rank, m.contribution_points, m.checkin_streak, m.last_checkin_date, m.joined_at
        FROM clans c
        JOIN clan_members m ON c.clan_id = m.clan_id
        WHERE m.guild_id = ? AND m.user_id = ?
        """
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (str(guild_id), str(user_id))) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_clans_in_guild(self, guild_id: int) -> List[Dict[str, Any]]:
        sql = """
        SELECT c.*, COUNT(m.user_id) as member_count
        FROM clans c
        LEFT JOIN clan_members m ON c.clan_id = m.clan_id
        WHERE c.guild_id = ?
        GROUP BY c.clan_id
        ORDER BY c.level DESC, c.exp DESC
        """
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (str(guild_id),)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_clan(self, clan_id: int, **fields) -> int:
        if not fields:
            return 0
        set_clauses = [f"{k} = ?" for k in fields.keys()]
        values = list(fields.values())
        values.append(clan_id)
        sql = f"UPDATE clans SET {', '.join(set_clauses)} WHERE clan_id = ?"
        async with self.connect() as db:
            cursor = await db.execute(sql, values)
            await db.commit()
            return cursor.rowcount

    async def add_clan_exp(self, clan_id: int, exp_to_add: int, weekly_exp_to_add: int) -> int:
        sql = "UPDATE clans SET exp = exp + ?, weekly_exp = weekly_exp + ? WHERE clan_id = ?"
        async with self.connect() as db:
            cursor = await db.execute(sql, (exp_to_add, weekly_exp_to_add, clan_id))
            await db.commit()
            return cursor.rowcount

    async def update_clan_level(self, clan_id: int, level: int, max_members: int, extra_voice_channel_id: Optional[int] = None) -> int:
        async with self.connect() as db:
            if extra_voice_channel_id:
                sql = "UPDATE clans SET level = ?, max_members = ?, extra_voice_channel_id = ? WHERE clan_id = ?"
                cursor = await db.execute(sql, (level, max_members, str(extra_voice_channel_id), clan_id))
            else:
                sql = "UPDATE clans SET level = ?, max_members = ? WHERE clan_id = ?"
                cursor = await db.execute(sql, (level, max_members, clan_id))
            await db.commit()
            return cursor.rowcount

    async def delete_clan(self, clan_id: int) -> int:
        async with self.connect() as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            # Xóa các liên kết để đảm bảo không còn dữ liệu mồ côi
            await db.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_requests WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_weekly_quests WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_milestones WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_logs WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_parties WHERE clan_id = ?", (clan_id,))
            cursor = await db.execute("DELETE FROM clans WHERE clan_id = ?", (clan_id,))
            await db.commit()
            return cursor.rowcount

    async def get_leaderboard(self, guild_id: int, criteria: str = "level", limit: int = 10) -> List[Dict[str, Any]]:
        order_by = "c.level DESC, c.exp DESC"
        if criteria == "weekly":
            order_by = "c.weekly_exp DESC, c.exp DESC"
        elif criteria == "members":
            order_by = "member_count DESC, c.level DESC"

        sql = f"""
        SELECT c.*, COUNT(m.user_id) as member_count
        FROM clans c
        LEFT JOIN clan_members m ON c.clan_id = m.clan_id
        WHERE c.guild_id = ?
        GROUP BY c.clan_id
        ORDER BY {order_by}
        LIMIT ?
        """
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (str(guild_id), limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def reset_weekly_exp(self, guild_id: Optional[int] = None) -> int:
        async with self.connect() as db:
            if guild_id:
                cursor = await db.execute("UPDATE clans SET weekly_exp = 0 WHERE guild_id = ?", (str(guild_id),))
            else:
                cursor = await db.execute("UPDATE clans SET weekly_exp = 0")
            await db.commit()
            return cursor.rowcount

    # =========================================================================
    # CLAN MEMBERS
    # =========================================================================
    async def add_member(self, guild_id: int, user_id: int, clan_id: int, rank: str = "MEMBER") -> int:
        now = int(time.time())
        sql = """
        INSERT INTO clan_members (
            guild_id, user_id, clan_id, rank, contribution_points, checkin_streak, joined_at
        ) VALUES (?, ?, ?, ?, 0, 0, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            clan_id = excluded.clan_id,
            rank = excluded.rank,
            contribution_points = 0,
            checkin_streak = 0,
            joined_at = excluded.joined_at
        """
        async with self.connect() as db:
            cursor = await db.execute(sql, (str(guild_id), str(user_id), clan_id, rank, now))
            await db.commit()
            return cursor.rowcount

    async def close(self):
        """Đóng kết nối cơ sở dữ liệu nếu có"""
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None

    async def get_member(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_members WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id))) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_members(self, clan_id: int, rank_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            if rank_filter:
                sql = """
                SELECT * FROM clan_members
                WHERE clan_id = ? AND rank = ?
                ORDER BY contribution_points DESC, joined_at ASC
                """
                async with db.execute(sql, (clan_id, rank_filter)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]
            else:
                sql = """
                SELECT * FROM clan_members
                WHERE clan_id = ?
                ORDER BY 
                    CASE rank
                        WHEN 'LEADER' THEN 1
                        WHEN 'CO_LEADER' THEN 2
                        WHEN 'OFFICER' THEN 3
                        WHEN 'MEMBER' THEN 4
                        ELSE 5
                    END ASC,
                    contribution_points DESC,
                    joined_at ASC
                """
                async with db.execute(sql, (clan_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

    async def get_member_count(self, clan_id: int) -> int:
        async with self.connect() as db:
            async with db.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (clan_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_rank_count(self, clan_id: int, rank: str) -> int:
        async with self.connect() as db:
            async with db.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id = ? AND rank = ?", (clan_id, rank)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def update_member_rank(self, guild_id: int, user_id: int, rank: str) -> int:
        async with self.connect() as db:
            cursor = await db.execute("UPDATE clan_members SET rank = ? WHERE guild_id = ? AND user_id = ?", (rank, str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def update_member_custom_title(self, guild_id: int, user_id: int, custom_title: Optional[str]) -> int:
        async with self.connect() as db:
            cursor = await db.execute("UPDATE clan_members SET custom_title = ? WHERE guild_id = ? AND user_id = ?", (custom_title, str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def add_milestone(self, clan_id: int, title: str, description: str) -> int:
        now = int(time.time())
        sql = "INSERT INTO clan_milestones (clan_id, title, description, achieved_at) VALUES (?, ?, ?, ?)"
        async with self.connect() as db:
            cursor = await db.execute(sql, (clan_id, title, description, now))
            await db.commit()
            return cursor.lastrowid

    async def get_clan_milestones(self, clan_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM clan_milestones WHERE clan_id = ? ORDER BY achieved_at DESC, milestone_id DESC LIMIT ?"
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (clan_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def add_contribution_points(self, guild_id: int, user_id: int, points: int) -> int:
        sql = "UPDATE clan_members SET contribution_points = contribution_points + ? WHERE guild_id = ? AND user_id = ?"
        async with self.connect() as db:
            cursor = await db.execute(sql, (points, str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def get_user_checkin_status(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        """Lấy ngày điểm danh gần nhất & streak độc lập (chống nhảy băng farm check-in)."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT last_checkin_date, checkin_streak FROM member_checkin_history WHERE guild_id = ? AND user_id = ?",
                (str(guild_id), str(user_id))
            ) as cursor:
                hist = await cursor.fetchone()
                if hist:
                    return dict(hist)
            async with db.execute(
                "SELECT last_checkin_date, checkin_streak FROM clan_members WHERE guild_id = ? AND user_id = ?",
                (str(guild_id), str(user_id))
            ) as cursor:
                mem = await cursor.fetchone()
                if mem and mem["last_checkin_date"]:
                    return {"last_checkin_date": mem["last_checkin_date"], "checkin_streak": mem["checkin_streak"] or 0}
        return {"last_checkin_date": None, "checkin_streak": 0}

    async def update_checkin(self, guild_id: int, user_id: int, date_str: str, streak: int) -> int:
        """Cập nhật điểm danh nguyên tử theo (guild_id, user_id, date_str), trả về 0 nếu hôm nay đã điểm danh."""
        async with self.connect() as db:
            async with db.execute(
                "SELECT last_checkin_date FROM member_checkin_history WHERE guild_id = ? AND user_id = ?",
                (str(guild_id), str(user_id))
            ) as cur:
                hist = await cur.fetchone()
                if hist and hist[0] == date_str:
                    return 0

            await db.execute(
                """
                INSERT INTO member_checkin_history (guild_id, user_id, last_checkin_date, checkin_streak)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    last_checkin_date = excluded.last_checkin_date,
                    checkin_streak = excluded.checkin_streak
                WHERE member_checkin_history.last_checkin_date != excluded.last_checkin_date
                """,
                (str(guild_id), str(user_id), date_str, streak)
            )
            cursor = await db.execute(
                """
                UPDATE clan_members
                SET last_checkin_date = ?, checkin_streak = ?, contribution_points = contribution_points + 10
                WHERE guild_id = ? AND user_id = ? AND (last_checkin_date IS NULL OR last_checkin_date != ?)
                """,
                (date_str, streak, str(guild_id), str(user_id), date_str)
            )
            await db.commit()
            return cursor.rowcount

    async def get_global_challenge_remaining(self, clan_id: int, cooldown_seconds: int = 43200) -> int:
        """Trả về số giây còn lại của cooldown gửi Thư Thách Đấu toàn server (0 nếu sẵn sàng)."""
        now = int(time.time())
        async with self.connect() as db:
            async with db.execute("SELECT last_global_challenge_at FROM clans WHERE clan_id = ?", (clan_id,)) as cur:
                row = await cur.fetchone()
                if not row or not row[0]:
                    return 0
                elapsed = now - int(row[0])
                return max(0, cooldown_seconds - elapsed)

    async def mark_global_challenge_sent(self, clan_id: int):
        """Ghi nhận timestamp băng vừa gửi Thư Thách Đấu toàn server."""
        now = int(time.time())
        async with self.connect() as db:
            await db.execute("UPDATE clans SET last_global_challenge_at = ? WHERE clan_id = ?", (now, clan_id))
            await db.commit()

    async def remove_member(self, guild_id: int, user_id: int) -> int:
        async with self.connect() as db:
            cursor = await db.execute("DELETE FROM clan_members WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def transfer_leadership(self, clan_id: int, guild_id: int, old_leader_id: int, new_leader_id: int):
        async with self.connect() as db:
            await db.execute("UPDATE clan_members SET rank = 'CO_LEADER' WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(old_leader_id)))
            await db.execute("UPDATE clan_members SET rank = 'LEADER' WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(new_leader_id)))
            await db.execute("UPDATE clans SET leader_id = ? WHERE clan_id = ?", (str(new_leader_id), clan_id))
            await db.commit()

    # =========================================================================
    # COOLDOWNS
    # =========================================================================
    async def get_cooldown(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        now = int(time.time())
        sql = "SELECT * FROM member_cooldowns WHERE guild_id = ? AND user_id = ? AND expires_at > ?"
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (str(guild_id), str(user_id), now)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def set_cooldown(self, guild_id: int, user_id: int, hours: int):
        if hours <= 0:
            await self.remove_cooldown(guild_id, user_id)
            return
        expires_at = int(time.time()) + (hours * 3600)
        sql = """
        INSERT INTO member_cooldowns (guild_id, user_id, expires_at)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET expires_at = excluded.expires_at
        """
        async with self.connect() as db:
            await db.execute(sql, (str(guild_id), str(user_id), expires_at))
            await db.commit()

    async def remove_cooldown(self, guild_id: int, user_id: int) -> int:
        async with self.connect() as db:
            cursor = await db.execute("DELETE FROM member_cooldowns WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def clean_expired_cooldowns(self) -> int:
        now = int(time.time())
        async with self.connect() as db:
            cursor = await db.execute("DELETE FROM member_cooldowns WHERE expires_at <= ?", (now,))
            await db.commit()
            return cursor.rowcount

    # =========================================================================
    # REQUESTS (INVITE / APPLY)
    # =========================================================================
    async def create_request(self, clan_id: int, guild_id: int, user_id: int, actor_id: int,
                             request_type: str, note: Optional[str] = None, message_id: Optional[int] = None,
                             expire_minutes: int = 15) -> int:
        now = int(time.time())
        expires_at = now + (expire_minutes * 60)
        sql = """
        INSERT INTO clan_requests (
            clan_id, guild_id, user_id, actor_id, request_type, note, message_id, expires_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with self.connect() as db:
            cursor = await db.execute(sql, (
                clan_id, str(guild_id), str(user_id), str(actor_id),
                request_type, note, str(message_id) if message_id else None, expires_at, now
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_request_by_id(self, request_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_requests WHERE request_id = ?", (request_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_request_status(self, request_id: int, new_status: str) -> int:
        """Cập nhật trạng thái an toàn chống Race Condition (chỉ đổi nếu đang PENDING)"""
        sql = "UPDATE clan_requests SET status = ? WHERE request_id = ? AND status = 'PENDING'"
        async with self.connect() as db:
            cursor = await db.execute(sql, (new_status, request_id))
            await db.commit()
            return cursor.rowcount

    async def get_expired_pending_requests(self) -> List[Dict[str, Any]]:
        now = int(time.time())
        sql = "SELECT * FROM clan_requests WHERE status = 'PENDING' AND expires_at <= ?"
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (now,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def has_pending_request(self, clan_id: int, user_id: int) -> bool:
        """Kiểm tra người dùng đã có đơn/lời mời đang chờ xử lý với băng này chưa."""
        now = int(time.time())
        sql = "SELECT 1 FROM clan_requests WHERE clan_id = ? AND user_id = ? AND status = 'PENDING' AND expires_at > ? LIMIT 1"
        async with self.connect() as db:
            async with db.execute(sql, (clan_id, str(user_id), now)) as cursor:
                return (await cursor.fetchone()) is not None

    async def mark_expired_requests(self) -> int:
        now = int(time.time())
        sql = "UPDATE clan_requests SET status = 'EXPIRED' WHERE status = 'PENDING' AND expires_at <= ?"
        async with self.connect() as db:
            cursor = await db.execute(sql, (now,))
            await db.commit()
            return cursor.rowcount

    # =========================================================================
    # CLAN LOGS
    # =========================================================================
    async def add_clan_log(self, clan_id: int, actor_id: int, action: str,
                           details: Optional[str] = None, target_id: Optional[int] = None):
        now = int(time.time())
        sql = """
        INSERT INTO clan_logs (clan_id, actor_id, target_id, action, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        async with self.connect() as db:
            await db.execute(sql, (clan_id, str(actor_id), str(target_id) if target_id else None, action, details, now))
            await db.commit()
        if self._log_dispatcher is not None:
            try:
                asyncio.create_task(self._log_dispatcher(clan_id, actor_id, action, details, target_id, now))
            except Exception as disp_err:
                logger.debug(f"Không thể lên lịch dispatch log kênh băng {clan_id}: {disp_err}")

    async def get_clan_logs(self, clan_id: int, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        offset = (page - 1) * page_size
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_logs WHERE clan_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            async with db.execute(sql, (clan_id, page_size, offset)) as cursor:
                rows = await cursor.fetchall()
                logs = [dict(r) for r in rows]

            async with db.execute("SELECT COUNT(*) FROM clan_logs WHERE clan_id = ?", (clan_id,)) as cursor:
                res = await cursor.fetchone()
                total = res[0] if res else 0

            total_pages = max(1, (total + page_size - 1) // page_size)
        return {"logs": logs, "total": total, "total_pages": total_pages, "page": page, "page_size": page_size}

    # =========================================================================
    # CLAN PARTIES (LFG)
    # =========================================================================
    async def create_party(self, clan_id: int, creator_id: int, channel_id: int,
                           message_id: int, title: str, max_slots: int, scheduled_at: Optional[int] = None) -> int:
        now = int(time.time())
        sql = """
        INSERT INTO clan_parties (
            clan_id, creator_id, channel_id, message_id, title, max_slots, scheduled_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with self.connect() as db:
            cursor = await db.execute(sql, (
                clan_id, str(creator_id), str(channel_id), str(message_id),
                title, max_slots, scheduled_at, now
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_party_by_id(self, party_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_parties WHERE party_id = ?", (party_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_party_by_message_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_parties WHERE message_id = ?", (str(message_id),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_party_participant(self, party_id: int, user_id: int, slot_type: str) -> int:
        now = int(time.time())
        sql = """
        INSERT INTO clan_party_participants (party_id, user_id, slot_type, joined_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(party_id, user_id) DO UPDATE SET slot_type = excluded.slot_type
        """
        async with self.connect() as db:
            cursor = await db.execute(sql, (party_id, str(user_id), slot_type, now))
            await db.commit()
            return cursor.rowcount

    async def remove_party_participant(self, party_id: int, user_id: int) -> int:
        async with self.connect() as db:
            cursor = await db.execute("DELETE FROM clan_party_participants WHERE party_id = ? AND user_id = ?", (party_id, str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def get_party_participants(self, party_id: int) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM clan_party_participants WHERE party_id = ? ORDER BY joined_at ASC"
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (party_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_party_status(self, party_id: int, status: str) -> int:
        async with self.connect() as db:
            cursor = await db.execute("UPDATE clan_parties SET status = ? WHERE party_id = ?", (status, party_id))
            await db.commit()
            return cursor.rowcount

    async def get_upcoming_parties_to_remind(self, current_time: int, window_seconds: int = 600) -> List[Dict[str, Any]]:
        max_time = current_time + window_seconds
        sql = """
        SELECT * FROM clan_parties
        WHERE status = 'OPEN' 
          AND reminded = 0 
          AND scheduled_at IS NOT NULL 
          AND scheduled_at > ? 
          AND scheduled_at <= ?
        """
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (current_time, max_time)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def mark_party_reminded(self, party_id: int) -> int:
        async with self.connect() as db:
            cursor = await db.execute("UPDATE clan_parties SET reminded = 1 WHERE party_id = ?", (party_id,))
            await db.commit()
            return cursor.rowcount

    # =========================================================================
    # WEEKLY QUESTS
    # =========================================================================
    async def ensure_weekly_quests(self, clan_id: int, week_key: str) -> List[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_weekly_quests WHERE clan_id = ? AND week_key = ?"
            async with db.execute(sql, (clan_id, week_key)) as cursor:
                existing = await cursor.fetchall()
                if existing:
                    return [dict(r) for r in existing]

            insert_sql = """
            INSERT INTO clan_weekly_quests (
                clan_id, week_key, quest_type, target_value, current_value, reward_exp, completed
            ) VALUES (?, ?, ?, ?, 0, ?, 0)
            """
            for quest in DEFAULT_WEEKLY_QUESTS:
                await db.execute(insert_sql, (
                    clan_id, week_key, quest["quest_type"], quest["target_value"], quest["reward_exp"]
                ))
            await db.commit()

            async with db.execute(sql, (clan_id, week_key)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_weekly_quests(self, clan_id: int, week_key: str) -> List[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_weekly_quests WHERE clan_id = ? AND week_key = ?"
            async with db.execute(sql, (clan_id, week_key)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def increment_quest_progress(self, clan_id: int, week_key: str, quest_type: str, amount: int) -> Dict[str, Any]:
        await self.ensure_weekly_quests(clan_id, week_key)

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_weekly_quests WHERE clan_id = ? AND week_key = ? AND quest_type = ?"
            async with db.execute(sql, (clan_id, week_key, quest_type)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"updated": False, "completed_now": False, "reward_exp": 0}

                quest = dict(row)
                if quest["completed"]:
                    return {"updated": False, "completed_now": False, "reward_exp": 0}

                new_value = quest["current_value"] + amount
                completed_now = new_value >= quest["target_value"]

                if completed_now:
                    await db.execute("UPDATE clan_weekly_quests SET current_value = ?, completed = 1 WHERE quest_id = ?", (new_value, quest["quest_id"]))
                else:
                    await db.execute("UPDATE clan_weekly_quests SET current_value = ? WHERE quest_id = ?", (new_value, quest["quest_id"]))
                await db.commit()

                return {
                    "updated": True,
                    "completed_now": completed_now,
                    "reward_exp": quest["reward_exp"] if completed_now else 0,
                    "quest_type": quest_type
                }

    async def update_request_message_id(self, request_id: int, message_id: int):
        async with self.connect() as db:
            await db.execute("UPDATE clan_requests SET message_id = ? WHERE request_id = ?", (str(message_id), request_id))
            await db.commit()

    # =========================================================================
    # NHIỆM VỤ NGÀY (DAILY QUESTS)
    # =========================================================================
    async def ensure_daily_quests(self, clan_id: int, date_key: str) -> List[Dict[str, Any]]:
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_daily_quests WHERE clan_id = ? AND date_key = ? ORDER BY quest_id ASC"
            async with db.execute(sql, (clan_id, date_key)) as cursor:
                existing = await cursor.fetchall()
                if existing:
                    return [dict(r) for r in existing]

            insert_sql = """
            INSERT OR IGNORE INTO clan_daily_quests (
                clan_id, date_key, quest_type, target_value, current_value, reward_exp, reward_coins, completed
            ) VALUES (?, ?, ?, ?, 0, ?, ?, 0)
            """
            for q in DEFAULT_DAILY_QUESTS:
                await db.execute(insert_sql, (
                    clan_id, date_key, q["quest_type"], q["target_value"], q["reward_exp"], q["reward_coins"]
                ))
            await db.commit()

            async with db.execute(sql, (clan_id, date_key)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def increment_daily_quest_progress(self, clan_id: int, date_key: str, quest_type: str, amount: int) -> Dict[str, Any]:
        await self.ensure_daily_quests(clan_id, date_key)
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_daily_quests WHERE clan_id = ? AND date_key = ? AND quest_type = ?"
            async with db.execute(sql, (clan_id, date_key, quest_type)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"updated": False, "completed_now": False, "reward_exp": 0, "reward_coins": 0}
                q = dict(row)
                if q["completed"]:
                    return {"updated": False, "completed_now": False, "reward_exp": 0, "reward_coins": 0}
                new_val = q["current_value"] + amount
                completed_now = new_val >= q["target_value"]
                await db.execute(
                    "UPDATE clan_daily_quests SET current_value = ?, completed = ? WHERE quest_id = ?",
                    (new_val, 1 if completed_now else 0, q["quest_id"])
                )
                await db.commit()
                return {
                    "updated": True,
                    "completed_now": completed_now,
                    "reward_exp": q["reward_exp"] if completed_now else 0,
                    "reward_coins": q["reward_coins"] if completed_now else 0,
                    "quest_type": quest_type,
                }

    # =========================================================================
    # LINH THÚ BĂNG ĐẢNG (CLAN PET)
    # =========================================================================
    async def get_clan_pet(self, clan_id: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin Linh Thú và tự động tính lazy decay (-5 mỗi 6 giờ)."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_pets WHERE clan_id = ?", (clan_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                pet = dict(row)

            now = int(time.time())
            elapsed = max(0, now - int(pet["last_decay_at"]))
            intervals = elapsed // (6 * 3600)
            if intervals > 0:
                decay = intervals * 5
                new_hunger = max(0, int(pet["hunger"]) - decay)
                new_mood = max(0, int(pet["mood"]) - decay)
                new_last_decay = int(pet["last_decay_at"]) + (intervals * 6 * 3600)
                await db.execute(
                    "UPDATE clan_pets SET hunger = ?, mood = ?, last_decay_at = ? WHERE clan_id = ?",
                    (new_hunger, new_mood, new_last_decay, clan_id)
                )
                await db.commit()
                pet["hunger"] = new_hunger
                pet["mood"] = new_mood
                pet["last_decay_at"] = new_last_decay

            try:
                pet["equipped"] = json.loads(pet.get("equipped_json") or "{}")
            except Exception:
                pet["equipped"] = {}
            return pet

    async def create_clan_pet(self, clan_id: int, species: str, name: str) -> Dict[str, Any]:
        now = int(time.time())
        async with self.connect() as db:
            await db.execute(
                """
                INSERT INTO clan_pets (
                    clan_id, species, name, exp, level, stage, hunger, mood,
                    pet_coins, equipped_json, allow_member_style, last_decay_at, created_at
                ) VALUES (?, ?, ?, 0, 1, 1, 80, 80, 100, '{}', 0, ?, ?)
                """,
                (clan_id, species, name[:24], now, now)
            )
            await db.commit()
        return await self.get_clan_pet(clan_id)

    async def update_clan_pet(self, clan_id: int, **kwargs):
        if not kwargs:
            return
        if "equipped" in kwargs:
            kwargs["equipped_json"] = json.dumps(kwargs.pop("equipped"))
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [clan_id]
        async with self.connect() as db:
            await db.execute(f"UPDATE clan_pets SET {fields} WHERE clan_id = ?", values)
            await db.commit()

    async def add_pet_coins(self, clan_id: int, coins: int):
        if coins <= 0:
            return
        async with self.connect() as db:
            await db.execute("UPDATE clan_pets SET pet_coins = pet_coins + ? WHERE clan_id = ?", (coins, clan_id))
            await db.commit()

    async def interact_with_pet(
        self,
        clan_id: int,
        hunger_delta: int,
        mood_delta: int,
        raw_exp: int,
        coin_cost: int,
        date_key: str,
        daily_exp_cap: int = 300,
    ) -> Dict[str, Any]:
        """Thực hiện Cho ăn / Vuốt ve / Tặng quà nguyên tử với trần Pet EXP theo ngày."""
        pet = await self.get_clan_pet(clan_id)
        if not pet:
            return {"ok": False, "error": "❌ Băng chưa nhận Linh Thú!"}
        if coin_cost > 0 and int(pet["pet_coins"]) < coin_cost:
            return {"ok": False, "error": f"❌ Quỹ Xu Linh Thú không đủ! Cần **{coin_cost}** Xu (hiện có **{pet['pet_coins']}** Xu)."}

        cur_daily_earned = int(pet.get("daily_exp_earned") or 0) if pet.get("daily_exp_date") == date_key else 0
        allowed_exp = max(0, min(raw_exp, daily_exp_cap - cur_daily_earned))
        new_daily_earned = cur_daily_earned + allowed_exp

        new_hunger = min(100, max(0, int(pet["hunger"]) + hunger_delta))
        new_mood = min(100, max(0, int(pet["mood"]) + mood_delta))
        new_exp = int(pet["exp"]) + allowed_exp
        new_coins = int(pet["pet_coins"]) - coin_cost

        old_stage = int(pet["stage"])
        old_level = int(pet["level"])
        lvl_info = get_pet_level_info(new_exp)

        async with self.connect() as db:
            await db.execute(
                """
                UPDATE clan_pets
                SET hunger = ?, mood = ?, exp = ?, level = ?, stage = ?,
                    pet_coins = ?, daily_exp_date = ?, daily_exp_earned = ?
                WHERE clan_id = ?
                """,
                (
                    new_hunger, new_mood, new_exp, lvl_info["level"], lvl_info["stage"],
                    new_coins, date_key, new_daily_earned, clan_id
                )
            )
            await db.commit()

        return {
            "ok": True,
            "added_exp": allowed_exp,
            "capped": allowed_exp < raw_exp,
            "old_level": old_level,
            "new_level": lvl_info["level"],
            "old_stage": old_stage,
            "new_stage": lvl_info["stage"],
            "evolved": lvl_info["stage"] > old_stage,
            "stage_name": lvl_info["stage_name"],
            "hunger": new_hunger,
            "mood": new_mood,
            "pet_coins": new_coins,
        }

    async def get_pet_inventory(self, clan_id: int) -> List[str]:
        async with self.connect() as db:
            async with db.execute("SELECT item_id FROM clan_pet_inventory WHERE clan_id = ?", (clan_id,)) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    async def buy_pet_item(self, clan_id: int, item_id: str, price: int) -> Dict[str, Any]:
        now = int(time.time())
        async with self.connect() as db:
            async with db.execute(
                "SELECT 1 FROM clan_pet_inventory WHERE clan_id = ? AND item_id = ?", (clan_id, item_id)
            ) as cur:
                if await cur.fetchone():
                    return {"ok": False, "error": "ℹ️ Băng của bạn đã sở hữu món đồ này trong Tủ Đồ rồi!"}

            cursor = await db.execute(
                "UPDATE clan_pets SET pet_coins = pet_coins - ? WHERE clan_id = ? AND pet_coins >= ?",
                (price, clan_id, price)
            )
            if cursor.rowcount != 1:
                return {"ok": False, "error": f"❌ Quỹ Xu Linh Thú không đủ (**{price} Xu**) để mua món đồ này!"}

            await db.execute(
                "INSERT INTO clan_pet_inventory (clan_id, item_id, purchased_at) VALUES (?, ?, ?)",
                (clan_id, item_id, now)
            )
            await db.commit()
            return {"ok": True}

    async def get_pet_action_cooldown(self, guild_id: int, user_id: int, action_type: str, cooldown_sec: int) -> int:
        now = int(time.time())
        async with self.connect() as db:
            async with db.execute(
                "SELECT last_used_at FROM clan_pet_cooldowns WHERE guild_id = ? AND user_id = ? AND action_type = ?",
                (str(guild_id), str(user_id), action_type)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return 0
                return max(0, cooldown_sec - (now - int(row[0])))

    async def set_pet_action_cooldown(self, guild_id: int, user_id: int, action_type: str):
        now = int(time.time())
        async with self.connect() as db:
            await db.execute(
                """
                INSERT INTO clan_pet_cooldowns (guild_id, user_id, action_type, last_used_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, action_type) DO UPDATE SET last_used_at = excluded.last_used_at
                """,
                (str(guild_id), str(user_id), action_type, now)
            )
            await db.commit()

    async def delete_clan_pet(self, clan_id: int):
        """Xóa toàn bộ dữ liệu Linh Thú & Tủ đồ của băng."""
        async with self.connect() as db:
            await db.execute("DELETE FROM clan_pet_inventory WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_pets WHERE clan_id = ?", (clan_id,))
            await db.commit()

    async def owner_buff_clan_exp(self, clan_id: int, exp_delta: int) -> Optional[Dict[str, Any]]:
        """Chủ Bot buff/điều chỉnh EXP băng và tự động tính lại Level & Sĩ số tối đa."""
        clan = await self.get_clan_by_id(clan_id)
        if not clan:
            return None
        new_exp = max(0, int(clan.get("exp", 0)) + exp_delta)
        new_weekly = max(0, int(clan.get("weekly_exp", 0)) + max(0, exp_delta))
        lvl_row = LEVELS[0]
        for lv in LEVELS:
            if new_exp >= lv["req_exp"]:
                lvl_row = lv
        async with self.connect() as db:
            await db.execute(
                "UPDATE clans SET exp = ?, weekly_exp = ?, level = ?, max_members = ? WHERE clan_id = ?",
                (new_exp, new_weekly, lvl_row["level"], lvl_row["max_members"], clan_id)
            )
            await db.commit()
        return await self.get_clan_by_id(clan_id)

    async def owner_buff_pet(
        self,
        clan_id: int,
        exp_delta: int = 0,
        coins_delta: int = 0,
        hunger_delta: int = 0,
        mood_delta: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Chủ Bot buff Pet EXP, Xu Linh Thú, Độ No và Độ Vui trực tiếp."""
        pet = await self.get_clan_pet(clan_id)
        if not pet:
            return None
        new_exp = max(0, int(pet.get("exp", 0)) + exp_delta)
        new_coins = max(0, int(pet.get("pet_coins", 0)) + coins_delta)
        new_hunger = min(100, max(0, int(pet.get("hunger", 80)) + hunger_delta))
        new_mood = min(100, max(0, int(pet.get("mood", 80)) + mood_delta))
        info = get_pet_level_info(new_exp)
        async with self.connect() as db:
            await db.execute(
                "UPDATE clan_pets SET exp = ?, level = ?, stage = ?, pet_coins = ?, hunger = ?, mood = ? WHERE clan_id = ?",
                (new_exp, info["level"], info["stage"], new_coins, new_hunger, new_mood, clan_id)
            )
            await db.commit()
        return await self.get_clan_pet(clan_id)

    async def owner_set_pet_state(
        self,
        clan_id: int,
        species: Optional[str] = None,
        stage: Optional[int] = None,
        equipped: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Chủ Bot đặt trực tiếp chủng loại, giai đoạn (Stage 1..5) hoặc bộ đồ đang mặc để test nhanh."""
        pet = await self.get_clan_pet(clan_id)
        if not pet:
            sp = species or "cyber_cat"
            sp_name = PET_SPECIES.get(sp, {}).get("name", sp)
            pet = await self.create_clan_pet(clan_id, sp, f"Bé {sp_name}")

        new_species = species if species in PET_SPECIES else pet["species"]
        new_exp = int(pet.get("exp", 0))
        if stage is not None:
            st = max(1, min(5, int(stage)))
            stage_min_exp = {1: 0, 2: 128, 3: 1008, 4: 3828, 5: 10388}
            new_exp = stage_min_exp[st]

        info = get_pet_level_info(new_exp)
        new_equipped = dict(equipped if equipped is not None else (pet.get("equipped") or {}))
        unlocked_slots = set(info["unlocked_slots"])
        new_equipped = {k: v for k, v in new_equipped.items() if k in unlocked_slots and v}

        async with self.connect() as db:
            await db.execute(
                "UPDATE clan_pets SET species = ?, exp = ?, level = ?, stage = ?, equipped_json = ? WHERE clan_id = ?",
                (new_species, new_exp, info["level"], info["stage"], json.dumps(new_equipped, ensure_ascii=False), clan_id)
            )
            await db.commit()
        return await self.get_clan_pet(clan_id)

    async def owner_unlock_all_pet_items(self, clan_id: int, item_ids: List[str], bonus_coins: int = 10000) -> Optional[Dict[str, Any]]:
        """Chủ Bot mở khóa toàn bộ vật phẩm trong Cửa Hàng & tặng Xu cho băng để test phối đồ."""
        pet = await self.get_clan_pet(clan_id)
        if not pet:
            pet = await self.create_clan_pet(clan_id, "cyber_cat", "Bé Mèo Cyber")
        now = time.time()
        async with self.connect() as db:
            for item_id in item_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO clan_pet_inventory (clan_id, item_id, purchased_at) VALUES (?, ?, ?)",
                    (clan_id, item_id, now)
                )
            await db.execute(
                "UPDATE clan_pets SET pet_coins = pet_coins + ? WHERE clan_id = ?",
                (max(0, int(bonus_coins)), clan_id)
            )
            await db.commit()
        return await self.get_clan_pet(clan_id)
