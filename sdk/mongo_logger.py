import logging
import datetime
import socket
import traceback
from typing import Optional, Dict, Any
from pymongo import MongoClient
import threading
import queue
import time

class MongoHandler(logging.Handler):
    """
    MongoDB 日志处理器 (Handler)。
    
    该类继承自 python 标准库的 logging.Handler。
    它的主要功能是将 Python 程序产生的日志发送到 MongoDB 数据库中。
    
    为了不阻塞主程序的运行（例如支付接口不能因为写日志慢而卡顿），
    我们采用【异步批量写入】的策略：
    1. `emit` 方法只负责将日志放入内存队列（速度极快）。
    2. 后台启动一个 `_worker` 线程，专门负责从队列取数据并批量写入 MongoDB。
    """
    def __init__(self, 
                 mongo_uri: str = "mongodb://localhost:27017/",
                 db_name: str = "log_monitor",
                 collection_name: str = "app_logs",
                 service_name: str = "unknown_service",
                 batch_size: int = 10,
                 flush_interval: float = 1.0):
        """
        初始化 MongoHandler。

        Args:
            mongo_uri (str): MongoDB 连接字符串。
            db_name (str): 数据库名称。
            collection_name (str): 集合（表）名称。
            service_name (str): 当前服务的名称（用于在日志中标识来源）。
            batch_size (int): 批量写入的阈值。当队列积压达到此数量时，触发一次写入。
            flush_interval (float): 定时刷新间隔（秒）。即使未达到 batch_size，超时也会强制写入。
        """
        super().__init__()
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.service_name = service_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # 连接 MongoDB
        try:
            self.client = MongoClient(mongo_uri)
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            self.client = None
            
        # 初始化队列和后台线程
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def emit(self, record):
        """
        日志处理入口。
        
        当调用 logger.info() 等方法时，logging 库会回调此方法。
        我们在这里将日志记录 (LogRecord) 格式化为 JSON，并放入队列。
        """
        try:
            log_entry = self.format_record(record)
            self.queue.put(log_entry)
        except Exception:
            self.handleError(record)

    def format_record(self, record) -> Dict[str, Any]:
        """
        格式化日志记录。
        
        将 Python 的 LogRecord 对象转换为符合项目规范的字典 (JSON)。
        包括：UTC时间戳、服务名、日志级别、代码路径等。
        """
        # 处理异常堆栈信息 (如果有)
        exc_info = None
        if record.exc_info:
            exc_info = "".join(traceback.format_exception(*record.exc_info))
        
        # 获取额外字段 (通过 extra 参数传递的)
        metadata = getattr(record, "metadata", {})
        trace_id = getattr(record, "trace_id", None)
        
        # 如果消息不是字符串，强制转换
        msg = record.msg
        if not isinstance(msg, str):
            msg = str(msg)
            
        # 如果有参数，进行字符串格式化 (例如: logger.info("User %s", "Alice"))
        if record.args:
            try:
                msg = msg % record.args
            except:
                pass

        # 构建最终的日志文档结构
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z", # 统一使用 UTC ISO8601 格式
            "service_name": self.service_name,
            "level": record.levelname,
            "message": msg,
            "file_path": record.pathname,
            "line_number": record.lineno,
            "metadata": metadata
        }
        
        # 注入 Trace ID (用于链路追踪)
        if trace_id:
            log_entry["trace_id"] = trace_id
            
        # 将异常堆栈放入 metadata 中
        if exc_info:
            if "error_stack" not in log_entry["metadata"]:
                 log_entry["metadata"]["error_stack"] = exc_info
            
        return log_entry

    def _worker(self):
        """
        后台工作线程函数。
        
        持续循环从队列中取出日志，满足以下任一条件时写入数据库：
        1. 积攒的日志数量达到 batch_size。
        2. 距离上次写入时间超过 flush_interval。
        """
        batch = []
        last_flush = time.time()
        
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                # 尝试从队列获取数据，设置超时防止死锁
                try:
                    item = self.queue.get(timeout=0.1)
                    batch.append(item)
                except queue.Empty:
                    pass
                
                current_time = time.time()
                is_batch_full = len(batch) >= self.batch_size
                is_time_to_flush = (current_time - last_flush) >= self.flush_interval
                
                # 满足条件则执行批量写入
                if batch and (is_batch_full or is_time_to_flush):
                    self._flush_batch(batch)
                    batch = []
                    last_flush = current_time
                    
            except Exception as e:
                # 线程内错误打印到标准错误，不抛出以免线程退出
                print(f"MongoHandler worker error: {e}")
                
    def _flush_batch(self, batch):
        """执行实际的 MongoDB 插入操作"""
        if self.client and batch:
            try:
                self.collection.insert_many(batch)
            except Exception as e:
                print(f"Failed to insert logs to MongoDB: {e}")

    def close(self):
        """
        关闭资源。
        
        在程序退出时调用，确保队列中剩余的日志被处理，并关闭数据库连接。
        """
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        if self.client:
            self.client.close()
        super().close()

# 辅助函数：快速配置日志
def setup_logging(service_name: str, 
                  mongo_uri: str = "mongodb://localhost:27017/",
                  level=logging.INFO):
    """
    快速设置日志系统的辅助函数。
    
    Args:
        service_name: 服务名称。
        mongo_uri: MongoDB 地址。
        level: 日志级别。
    
    Returns:
        logging.Logger: 配置好的 logger 对象。
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    
    # 添加 MongoDB 处理器
    mongo_handler = MongoHandler(mongo_uri=mongo_uri, service_name=service_name)
    logger.addHandler(mongo_handler)
    
    # 添加控制台处理器 (方便调试，同时在终端看到日志)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    return logger
