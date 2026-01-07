import sys
import os
import time
import random
import uuid
from faker import Faker

# 将项目根目录添加到 python 路径，以便我们可以导入 sdk 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.mongo_logger import setup_logging

# 初始化 Faker，用于生成虚假数据（如IP、用户名等）
fake = Faker()

# 定义模拟的服务名称列表
SERVICES = ["auth-service", "payment-service", "data-processor", "frontend-api"]
# 定义日志级别及其出现的权重（ERROR 出现的概率较低，INFO 较高）
LEVELS = ["INFO", "INFO", "INFO", "WARNING", "ERROR", "DEBUG"]

def generate_metadata(service):
    """
    根据服务类型生成特定的元数据 (Metadata)。
    
    例如：支付服务需要记录金额和货币，认证服务需要记录用户IP。
    """
    meta = {
        "host": f"server-{random.randint(1, 5)}", # 模拟不同的服务器主机
        "region": random.choice(["us-east-1", "eu-west-1", "ap-northeast-1"]), # 模拟不同的区域
    }
    
    if service == "payment-service":
        meta["amount"] = round(random.uniform(10.0, 1000.0), 2)
        meta["currency"] = "USD"
        meta["user_id"] = random.randint(1000, 9999)
    elif service == "auth-service":
        meta["user_id"] = random.randint(1000, 9999)
        meta["ip"] = fake.ipv4()
        
    return meta

def simulate_logs():
    """
    主模拟循环。
    
    不断随机选择服务、随机生成日志级别，并调用 SDK 写入日志。
    """
    print("Starting log simulation... Press Ctrl+C to stop. (按 Ctrl+C 停止)")
    
    # 为每个服务预先初始化 logger 对象
    loggers = {name: setup_logging(name) for name in SERVICES}
    
    try:
        while True:
            # 随机选择一个服务
            service = random.choice(SERVICES)
            logger = loggers[service]
            # 随机选择一个日志级别
            level = random.choice(LEVELS)
            
            # 生成唯一的 Trace ID (用于链路追踪)
            trace_id = str(uuid.uuid4())
            # 生成业务相关的元数据
            metadata = generate_metadata(service)
            
            # 将 trace_id 和 metadata 放入 extra 字典中，SDK 会自动处理
            extra = {"trace_id": trace_id, "metadata": metadata}
            
            if level == "INFO":
                logger.info(f"Operation {fake.word()} completed: {fake.sentence()}", extra=extra)
            elif level == "WARNING":
                logger.warning(f"Resource {fake.word()} is running low: {fake.sentence()}", extra=extra)
            elif level == "ERROR":
                try:
                    # 模拟一个除零异常，以测试堆栈捕获功能
                    1 / 0
                except Exception:
                    # exc_info=True 会自动捕获当前的异常堆栈
                    logger.error(f"Critical failure in {fake.word()}", exc_info=True, extra=extra)
            elif level == "DEBUG":
                logger.debug(f"Variable state: {fake.pydict()}", extra=extra)
                
            # 随机休眠一小段时间，控制日志生成速率
            time.sleep(random.uniform(0.1, 0.5))
            
    except KeyboardInterrupt:
        print("\nStopping simulation...")

if __name__ == "__main__":
    simulate_logs()
