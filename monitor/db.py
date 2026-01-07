from pymongo import MongoClient
import datetime
import pandas as pd

import sys
import os
from bson import ObjectId

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config

class LogDatabase:
    """
    数据库访问层 (DAO) 类。
    """
    def __init__(self):
        """
        初始化数据库连接。
        """
        try:
            # 设置 serverSelectionTimeoutMS 以避免连接不存在的 DB 时长时间挂起
            self.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=2000)
            # 触发一次即时的连接检查
            self.client.server_info()
            self.db = self.client[Config.DB_NAME]
            self.collection = self.db[Config.COLLECTION_NAME]
            self.connected = True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            self.collection = None

    def get_log_by_id(self, log_id):
        """
        根据 ID 获取单条日志。
        """
        if not self.connected or not log_id:
            return None
        try:
            return self.collection.find_one({"_id": ObjectId(log_id)})
        except Exception:
            return None

    def get_logs(self, limit=100, service=None, level=None, start_time=None, end_time=None, search_text=None):
        """
        根据条件获取日志列表。
        
        Args:
            limit (int): 返回的最大日志条数。
            service (str): 按服务名称筛选 ("All" 表示不筛选)。
            level (str): 按日志级别筛选 ("All" 表示不筛选)。
            start_time (datetime): 开始时间。
            end_time (datetime): 结束时间。
            search_text (str): 消息内容的关键词（支持正则模糊搜索）。
            
        Returns:
            pd.DataFrame: 包含日志数据的 Pandas DataFrame。
        """
        if not self.connected:
            return pd.DataFrame()
            
        # 构建 MongoDB 查询字典
        query = {}
        
        if service and service != "All":
            query["service_name"] = service
            
        if level and level != "All":
            query["level"] = level
            
        # 时间范围查询
        if start_time or end_time:
            query["timestamp"] = {}
            if start_time:
                query["timestamp"]["$gte"] = start_time.isoformat()
            if end_time:
                query["timestamp"]["$lte"] = end_time.isoformat()
            # 如果构建后的 dict 为空（例如参数都为None），则删除该键
            if not query["timestamp"]:
                del query["timestamp"]
                
        # 关键词搜索 (不区分大小写)
        if search_text:
            query["message"] = {"$regex": search_text, "$options": "i"}

        # 执行查询，按时间倒序排列
        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        logs = list(cursor)
        
        # 将 ObjectId 转换为字符串，以免 Pandas 显示为对象
        for log in logs:
            if "_id" in log:
                log["_id"] = str(log["_id"])
                
        return pd.DataFrame(logs)

    def get_stats(self):
        """
        获取日志统计信息。
        
        Returns:
            dict: 包含总日志数、错误数、各服务日志分布的字典。
        """
        if not self.connected:
             return {
                "total_logs": 0,
                "error_logs": 0,
                "service_counts": {}
            }

        # 统计总数
        total_logs = self.collection.count_documents({})
        # 统计错误总数
        error_logs = self.collection.count_documents({"level": "ERROR"})
        
        # 使用聚合管道 (Aggregation Pipeline) 按服务分组统计
        # 相当于 SQL: SELECT service_name, COUNT(*) FROM logs GROUP BY service_name
        pipeline = [
            {"$group": {"_id": "$service_name", "count": {"$sum": 1}}}
        ]
        service_counts = list(self.collection.aggregate(pipeline))
        
        return {
            "total_logs": total_logs,
            "error_logs": error_logs,
            "service_counts": {item["_id"]: item["count"] for item in service_counts}
        }

    def get_error_trend(self):
        """
        获取过去24小时的错误趋势数据。
        
        用于生成折线图。
        """
        if not self.connected:
            return pd.DataFrame()
            
        # 简单实现：获取最近24小时的所有 ERROR 日志，然后在 Pandas 中进行重采样(Resample)
        yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
        cursor = self.collection.find(
            {"level": "ERROR", "timestamp": {"$gte": yesterday}},
            {"timestamp": 1, "service_name": 1} # 仅投影需要的字段以优化性能
        )
        return pd.DataFrame(list(cursor))
