import asyncio
import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("CronScheduler")

class GoldenHourScheduler:
    def __init__(self):
        self.is_running = False
        self.schedules = []
        self.task = None

    def add_schedule(self, task_type: str, account_id: str, target_time: str, payload: dict = None):
        """Thêm một lịch hẹn (VD target_time = '11:30' hoặc '20:00')."""
        self.schedules.append({
            "id": f"sched_{int(time.time()*1000)}",
            "task_type": task_type, # "boost", "flashsale", "video"
            "account_id": account_id,
            "target_time": target_time, # "HH:MM"
            "payload": payload or {},
            "status": "Chờ kích hoạt",
            "last_executed": None
        })

    def get_schedules(self) -> List[Dict[str, Any]]:
        return self.schedules

    def remove_schedule(self, sched_id: str):
        self.schedules = [s for s in self.schedules if s["id"] != sched_id]

    async def start_loop(self, executor_callback=None, log_callback=None):
        self.is_running = True
        if log_callback:
            await log_callback("⏰ Bộ hẹn giờ Khung Giờ Vàng (Cron Scheduler) đã được kích hoạt!")

        while self.is_running:
            now_str = datetime.now().strftime("%H:%M")
            today_date = datetime.now().strftime("%Y-%m-%d")

            for item in self.schedules:
                if item["target_time"] == now_str and item["last_executed"] != today_date:
                    item["last_executed"] = today_date
                    item["status"] = f"Đã chạy ({now_str})"
                    
                    if log_callback:
                        await log_callback(f"🎯 ĐẾN GIỜ VÀNG [{now_str}]: Tự động kích hoạt tác vụ '{item['task_type'].upper()}' cho Shop {item['account_id']}!")
                    
                    if executor_callback:
                        try:
                            await executor_callback(item["task_type"], item["account_id"], item["payload"])
                        except Exception as e:
                            logger.error(f"Lỗi thực thi scheduler task: {e}")

            await asyncio.sleep(30)

    def stop(self):
        self.is_running = False

cron_scheduler = GoldenHourScheduler()
