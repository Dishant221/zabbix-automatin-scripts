import pylightxl as xl
import os

from host_HG_modification_from_cloud_insight import BaseDirectory
xl_file_path = os.path.join(BaseDirectory,"DATA","INPUT","VM details report - not monitored by ZB_021926.xlsx")  

db = xl.readxl(fn=xl_file_path)
print(db.ws_names)