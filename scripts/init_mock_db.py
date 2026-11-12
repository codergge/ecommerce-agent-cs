"""
生成业务模拟数据库（命令行入口）

实际造数逻辑在 db/seed_mock_data.py，这里只做路径处理，方便在项目根目录直接执行：

    python scripts/init_mock_db.py            # 首次生成
    python scripts/init_mock_db.py --rebuild  # 删库重建

产物：
    data/ecommerce.db    业务数据库（订单 120 / 物流 111 / 库存 120）
    data/seed_data.sql   纯 INSERT 脚本，可用 Navicat、DB Browser 直接查看
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from db.seed_mock_data import main  # noqa: E402

if __name__ == "__main__":
    main()
