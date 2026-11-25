"""
Async SQLite Database Manager using aiosqlite with WAL mode
"""

import aiosqlite
from pathlib import Path
import time
from typing import Optional, Dict, List, Any
from utils.logger import setup_logging
from utils.constants import DEFAULT_WEEKLY_QUESTS

logger = setup_logging("Database")

class DatabaseManager:
    """Quản lý kết nối SQLite bất đồng bộ và thực thi truy vấn"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Khởi tạo file cơ sở dữ liệu, kích hoạt WAL mode và chạy migrations"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
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
                leave_cooldown_hours INTEGER DEFAULT 24,
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

            -- Các chỉ mục tối ưu hiệu năng
            CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id);
            CREATE INDEX IF NOT EXISTS idx_clan_logs_clan_time ON clan_logs(clan_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_clan_requests_status ON clan_requests(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_clan_parties_reminder ON clan_parties(status, reminded, scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_weekly_quests_clan_week ON clan_weekly_quests(clan_id, week_key);
            """

            await db.executescript(schema)
            await db.commit()

            # Migration: thêm secondary_color_hex nếu chưa có
            try:
                await db.execute("ALTER TABLE clans ADD COLUMN secondary_color_hex TEXT")
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

        logger.info(f"Đã kết nối và khởi tạo schema SQLite (WAL Mode) tại: {self.db_path}")

    # =========================================================================
    # GUILD CONFIGS
    # =========================================================================
    async def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
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

    # =========================================================================
    # CLANS CRUD
    # =========================================================================
    async def create_clan(self, guild_id: int, name: str, tag: str, description: str,
                          role_id: int, text_channel_id: int, voice_channel_id: int,
                          leader_id: int, color_hex: str = "#5865F2") -> int:
        now = int(time.time())
        sql = """
        INSERT INTO clans (
            guild_id, name, tag, description, role_id, text_channel_id, voice_channel_id, leader_id, color_hex, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (
                str(guild_id), name, tag, description, str(role_id),
                str(text_channel_id), str(voice_channel_id), str(leader_id), color_hex, now
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_clan_by_id(self, clan_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE clan_id = ?", (clan_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_name(self, guild_id: int, name: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE guild_id = ? AND LOWER(name) = LOWER(?)", (str(guild_id), name.strip())) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_tag(self, guild_id: int, tag: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE guild_id = ? AND LOWER(tag) = LOWER(?)", (str(guild_id), tag.strip())) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_role_id(self, role_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clans WHERE role_id = ?", (str(role_id),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_channel_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM clans WHERE text_channel_id = ? OR voice_channel_id = ? OR extra_voice_channel_id = ?"
            async with db.execute(query, (str(channel_id), str(channel_id), str(channel_id))) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_by_member(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT c.*, m.rank, m.contribution_points, m.checkin_streak, m.last_checkin_date, m.joined_at
        FROM clans c
        JOIN clan_members m ON c.clan_id = m.clan_id
        WHERE m.guild_id = ? AND m.user_id = ?
        """
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, values)
            await db.commit()
            return cursor.rowcount

    async def add_clan_exp(self, clan_id: int, exp_to_add: int, weekly_exp_to_add: int) -> int:
        sql = "UPDATE clans SET exp = exp + ?, weekly_exp = weekly_exp + ? WHERE clan_id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (exp_to_add, weekly_exp_to_add, clan_id))
            await db.commit()
            return cursor.rowcount

    async def update_clan_level(self, clan_id: int, level: int, max_members: int, extra_voice_channel_id: Optional[int] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            if extra_voice_channel_id:
                sql = "UPDATE clans SET level = ?, max_members = ?, extra_voice_channel_id = ? WHERE clan_id = ?"
                cursor = await db.execute(sql, (level, max_members, str(extra_voice_channel_id), clan_id))
            else:
                sql = "UPDATE clans SET level = ?, max_members = ? WHERE clan_id = ?"
                cursor = await db.execute(sql, (level, max_members, clan_id))
            await db.commit()
            return cursor.rowcount

    async def delete_clan(self, clan_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            # Xóa các liên kết để đảm bảo không còn dữ liệu mồ côi
            await db.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_requests WHERE clan_id = ?", (clan_id,))
            await db.execute("DELETE FROM clan_weekly_quests WHERE clan_id = ?", (clan_id,))
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (str(guild_id), limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def reset_weekly_exp(self, guild_id: Optional[int] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_members WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id))) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_clan_members(self, clan_id: int, rank_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (clan_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_rank_count(self, clan_id: int, rank: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id = ? AND rank = ?", (clan_id, rank)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def update_member_rank(self, guild_id: int, user_id: int, rank: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE clan_members SET rank = ? WHERE guild_id = ? AND user_id = ?", (rank, str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def add_contribution_points(self, guild_id: int, user_id: int, points: int) -> int:
        sql = "UPDATE clan_members SET contribution_points = contribution_points + ? WHERE guild_id = ? AND user_id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (points, str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def update_checkin(self, guild_id: int, user_id: int, date_str: str, streak: int) -> int:
        sql = """
        UPDATE clan_members 
        SET last_checkin_date = ?, checkin_streak = ?, contribution_points = contribution_points + 10
        WHERE guild_id = ? AND user_id = ?
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (date_str, streak, str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def remove_member(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM clan_members WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def transfer_leadership(self, clan_id: int, guild_id: int, old_leader_id: int, new_leader_id: int):
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (str(guild_id), str(user_id), now)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def set_cooldown(self, guild_id: int, user_id: int, hours: int):
        expires_at = int(time.time()) + (hours * 3600)
        sql = """
        INSERT INTO member_cooldowns (guild_id, user_id, expires_at)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET expires_at = excluded.expires_at
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, (str(guild_id), str(user_id), expires_at))
            await db.commit()

    async def remove_cooldown(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM member_cooldowns WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def clean_expired_cooldowns(self) -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (
                clan_id, str(guild_id), str(user_id), str(actor_id),
                request_type, note, str(message_id) if message_id else None, expires_at, now
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_request_by_id(self, request_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_requests WHERE request_id = ?", (request_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_request_status(self, request_id: int, new_status: str) -> int:
        """Cập nhật trạng thái an toàn chống Race Condition (chỉ đổi nếu đang PENDING)"""
        sql = "UPDATE clan_requests SET status = ? WHERE request_id = ? AND status = 'PENDING'"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (new_status, request_id))
            await db.commit()
            return cursor.rowcount

    async def get_expired_pending_requests(self) -> List[Dict[str, Any]]:
        now = int(time.time())
        sql = "SELECT * FROM clan_requests WHERE status = 'PENDING' AND expires_at <= ?"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (now,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def mark_expired_requests(self) -> int:
        now = int(time.time())
        sql = "UPDATE clan_requests SET status = 'EXPIRED' WHERE status = 'PENDING' AND expires_at <= ?"
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, (clan_id, str(actor_id), str(target_id) if target_id else None, action, details, now))
            await db.commit()

    async def get_clan_logs(self, clan_id: int, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        offset = (page - 1) * page_size
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_logs WHERE clan_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            async with db.execute(sql, (clan_id, page_size, offset)) as cursor:
                rows = await cursor.fetchall()
                logs = [dict(r) for r in rows]

            async with db.execute("SELECT COUNT(*) FROM clan_logs WHERE clan_id = ?", (clan_id,)) as cursor:
                res = await cursor.fetchone()
                total = res[0] if res else 0

        return {"logs": logs, "total": total, "page": page, "page_size": page_size}

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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (
                clan_id, str(creator_id), str(channel_id), str(message_id),
                title, max_slots, scheduled_at, now
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_party_by_id(self, party_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM clan_parties WHERE party_id = ?", (party_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_party_by_message_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, (party_id, str(user_id), slot_type, now))
            await db.commit()
            return cursor.rowcount

    async def remove_party_participant(self, party_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM clan_party_participants WHERE party_id = ? AND user_id = ?", (party_id, str(user_id)))
            await db.commit()
            return cursor.rowcount

    async def get_party_participants(self, party_id: int) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM clan_party_participants WHERE party_id = ? ORDER BY joined_at ASC"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (party_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_party_status(self, party_id: int, status: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (current_time, max_time)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def mark_party_reminded(self, party_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE clan_parties SET reminded = 1 WHERE party_id = ?", (party_id,))
            await db.commit()
            return cursor.rowcount

    # =========================================================================
    # WEEKLY QUESTS
    # =========================================================================
    async def ensure_weekly_quests(self, clan_id: int, week_key: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT * FROM clan_weekly_quests WHERE clan_id = ? AND week_key = ?"
            async with db.execute(sql, (clan_id, week_key)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def increment_quest_progress(self, clan_id: int, week_key: str, quest_type: str, amount: int) -> Dict[str, Any]:
        await self.ensure_weekly_quests(clan_id, week_key)

        async with aiosqlite.connect(self.db_path) as db:
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
