from trendradar.storage import get_storage_manager
import json

def debug_api():
    sm = get_storage_manager(
        backend_type="local", 
        data_dir="output",
        timezone="Asia/Kolkata"
    )
    
    data = sm.get_today_all_data(None)
    if not data:
        print("Data is None")
        return
        
    print(f"Date: {data.date}")
    print(f"Items found: {sum(len(v) for v in data.items.values())}")
    
    for source_id, items in data.items.items():
        print(f"Source: {source_id}, Count: {len(items)}")
        if items:
            print(f"  First item: {items[0].title} | Categories: {items[0].categories}")

if __name__ == "__main__":
    debug_api()
