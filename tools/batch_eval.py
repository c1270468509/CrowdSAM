import os
import subprocess
import concurrent.futures
import argparse
import json
import yaml
def run_script(start_idx, end_idx, save_dir, exec_file,config_file, options):
    cmd = [
        'srun', '-c', '4', '--mem', '40G', '--gres=gpu:1', 
        'python', exec_file, 
        '--config_file', config_file,
        '--output_dir', f'vis_output/{save_dir}', 
        *options.split(), 
        '--start_idx', str(start_idx), 
        '--num_imgs', str(end_idx)
    ]
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd)
def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config
def merge_json(json_files):    # Initialize an empty list to hold merged data
    merged_data = []
    # Load and merge JSON files
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            merged_data.extend(data)
    # Write merged data to the specified output JSON file
    return merged_data
def convert_to_coco(det_result, gt_js):
    #
    id_ = 0
    annotations = []
    category_id = 1
    
    image_items = gt_js['images']
    categories = gt_js['categories']
    for img_item in image_items:
        img_item['id'] = img_item['file_name'][:-4]

    for k,item in enumerate(det_result):
        #convert image id to integer by defaults
        if image_items != []:
            image_id = image_items[k]['id']
        else:
            image_id = item['image_id']
        scores = item['scores']
        boxes =  item["boxes"] 
        for score,box in zip(scores, boxes):
            area = (box[3] - box[1]) * (box[2] - box[0])
            box [2] = box[2] - box[0]
            box[3] = box[3] - box[1]
            annot = {"category_id":category_id, "bbox":box, "image_id":image_id, "iscrowd":False, "area": area, "id":id_, "score":score}
            id_ += 1
            annotations.append(annot)
    final_result= {"images":image_items, "annotations":annotations, 'categories':categories}
    return final_result

def main():
    parser = argparse.ArgumentParser(description="Run multiple Python scripts concurrently")
    parser.add_argument('--num_nodes', type=int,  default=4, help='Number of nodes to use')
    # parser.add_argument('--annot_file', type=str, default="datasets/crowdhuman/midval_visible_100.json", help='Annotation file path')
    # parser.add_argument('--odgt_file', type=str, default="datasets/crowdhuman/annotation_val.odgt", help='ODGT file path')
    parser.add_argument('--config_file', default='./configs/crowdhuman.yaml')
    parser.add_argument('--options', type=str, default="", help='Additional options for the Python script')
    args = parser.parse_args()
    config = load_config(args.config_file)
    
    #load yaml
    gt_js = json.load(open(config['data']['json_file']))
    num_imgs = len(gt_js['images'])
    num_nodes = args.num_nodes
    batch_size = num_imgs // num_nodes
    annot_file = config['data']['json_file']
    odgt_file = config['data']['odgt_file']
    exec_file = 'test.py'
    config_file = args.config_file
    options = args.options
    

    # Run the python scripts concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_nodes) as executor:
        futures = []
        for i in range(num_nodes):
            start_idx = i * batch_size
            end_idx = (i + 1) * batch_size
            save_dir = f"batch_run_{i}"
            print(f"{start_idx}, {end_idx}, {save_dir}")
            futures.append(executor.submit(run_script, start_idx, end_idx, save_dir, exec_file, config_file, options))

        # Wait for all futures to complete
        concurrent.futures.wait(futures)

    # Merge JSON results
    json_list = [f"vis_output/batch_run_{i}/result.json" for i in range(num_nodes)]
    # merge_cmd = f"python tools/merge_json.py final.json {json_list}"
    merged_result = merge_json(json_list)
    

    coco_json = convert_to_coco(merged_result, gt_js)
    json.dump(coco_json, open('test.json','w'), ensure_ascii=True)
    # print(f"Merging results with command: {merge_cmd}")
    # subprocess.run(merge_cmd, shell=True)

    # Test with visible flag
    # convert_cmd = f"python tools/convert2coco.py -d final.json -o test.json -g {annot_file} --ref_img_id_type str"
    eval_cmd = f"python tools/crowdhuman_eval.py -d test.json -g {odgt_file} --remove_empty_gt --visible_flag"
    # print(f"Converting with command: {convert_cmd}")
    # subprocess.run(convert_cmd, shell=True)
    print(f"Evaluating with command: {eval_cmd}")
    subprocess.run(eval_cmd, shell=True)

    # Remove temporary test.json file
    os.remove("test.json")
    print("All processes done")

if __name__ == "__main__":
    main()