#!/usr/bin/env python3
"""
Generate data files for the landing page from Result_Official folder.
This script processes all result JSON files and creates structured data for the playground.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
import statistics

# Get the base directory (one level up from landing_page)
BASE_DIR = Path(__file__).parent.parent
RESULT_DIR = BASE_DIR / "Result_Official"
OUTPUT_DIR = Path(__file__).parent

# Map file naming to our keys
DATASET_MAP = {
    "T_Cell": "T_Cell",
    "TF_Cell": "TF_Cell",
    "Hela_regular_mode": "Hela_regular",
    "Hela_timesaving_mode": "Hela_timesaving",
    "rat_myocyte": "rat_myocyte"
}

def extract_metadata_from_filename(filename):
    """Extract optimizer, dataset, mode, race_type, batch, and hidden_frac from filename."""
    parts = filename.replace(".json", "").split("_")
    
    # Find optimizer (first part before dataset name)
    optimizer = parts[0]
    
    # Find dataset
    dataset = None
    for ds_key in DATASET_MAP.keys():
        if ds_key in filename:
            dataset = DATASET_MAP[ds_key]
            break
    
    # Find mode (Easy or Hard)
    mode = "Regular" if "Easy" in filename else "Hard"
    
    # Find race type
    race_type = "Hide_The_Label" if "Hide_The_Label" in filename else "Open_Race"
    
    # Find batch size
    batch = None
    for part in parts:
        if part.startswith("Batch"):
            batch = int(part.replace("Batch", ""))
            break
    
    # Find hidden percentage
    hidden_frac = None
    for i, part in enumerate(parts):
        if part == "Percentage":
            try:
                hidden_frac = float(parts[i + 1])
            except (IndexError, ValueError):
                pass
            break
    
    return {
        "optimizer": optimizer,
        "dataset": dataset,
        "mode": mode,
        "race_type": race_type,
        "batch": batch,
        "hidden_frac": hidden_frac
    }


def process_hide_label_file(filepath):
    """Process a Hide-the-Label result file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    results = {}
    
    # Navigate the structure
    if 'tournament_results' in data:
        for tournament in data['tournament_results']:
            optimizer_names = tournament.get('optimizer_names', [])
            
            # Collect steps to target for each optimizer across all competitions
            optimizer_steps = defaultdict(list)
            
            for competition in tournament.get('competitions', []):
                opt_results = competition.get('optimizer_results', {})
                for opt_name, opt_data in opt_results.items():
                    steps = opt_data.get('steps_to_target')
                    if steps is not None:
                        optimizer_steps[opt_name].append(steps)
            
            # Calculate mean steps for each optimizer
            for opt_name, steps_list in optimizer_steps.items():
                if steps_list:
                    results[opt_name] = {
                        'mean_steps': statistics.mean(steps_list),
                        'median_steps': statistics.median(steps_list),
                        'min_steps': min(steps_list),
                        'max_steps': max(steps_list),
                        'count': len(steps_list)
                    }
    
    return results


def process_open_race_file(filepath):
    """Process an Open Race result file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    results = {}
    
    optimizer_names = data.get('optimizer_names', [])
    
    # Collect optimization histories for each optimizer across all competitions
    optimizer_histories = defaultdict(list)
    
    for competition in data.get('competitions', []):
        opt_results = competition.get('optimizer_results', {})
        for opt_name, opt_data in opt_results.items():
            history = opt_data.get('optimization_history', [])
            optimizer_histories[opt_name].append(history)
    
    # Average the histories across competitions
    for opt_name, histories in optimizer_histories.items():
        if not histories:
            continue
        
        # Find the maximum number of steps across all competitions
        max_steps = max(len(h) for h in histories)
        
        # For each step, average the best_value_so_far across all competitions
        steps = []
        values = []
        
        for step_idx in range(max_steps):
            step_values = []
            for history in histories:
                if step_idx < len(history):
                    best_val = history[step_idx].get('best_value_so_far')
                    if best_val is not None:
                        step_values.append(best_val)
            
            if step_values:
                steps.append(step_idx)
                values.append(statistics.mean(step_values))
        
        results[opt_name] = {
            'steps': steps,
            'values': values,
            'final_best': values[-1] if values else None
        }
    
    return results


def generate_data_files():
    """Generate JSON data files for the landing page."""
    
    # Structure: data[hidden_frac][mode][race_type][batch][dataset][optimizer] = results
    all_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))))
    
    # Walk through the Result_Official directory
    for hidden_frac_dir in RESULT_DIR.iterdir():
        if not hidden_frac_dir.is_dir():
            continue
        
        # Extract hidden fraction from directory name (hiddenfrac95 -> 0.95)
        hidden_frac_str = hidden_frac_dir.name.replace("hiddenfrac", "")
        if hidden_frac_str == "95":
            hidden_frac = 0.95
        elif hidden_frac_str == "99":
            hidden_frac = 0.99
        else:
            continue
        
        # Process each mode (Hard_Mode, Regular_Mode)
        for mode_dir in hidden_frac_dir.iterdir():
            if not mode_dir.is_dir():
                continue
            
            mode = "Hard" if "Hard" in mode_dir.name else "Regular"
            
            # Process each race type (Hide_The_Label, Open_Race)
            for race_dir in mode_dir.iterdir():
                if not race_dir.is_dir():
                    continue
                
                race_type = "Hide_The_Label" if "Hide_The_Label" in race_dir.name else "Open_Race"
                
                # Process each JSON file
                for json_file in race_dir.glob("*.json"):
                    print(f"Processing: {json_file.relative_to(RESULT_DIR)}")
                    
                    metadata = extract_metadata_from_filename(json_file.name)
                    
                    if race_type == "Hide_The_Label":
                        results = process_hide_label_file(json_file)
                    else:  # Open_Race
                        results = process_open_race_file(json_file)
                    
                    # Store results in the structure
                    dataset = metadata['dataset']
                    batch = metadata['batch']
                    
                    for opt_name, opt_results in results.items():
                        all_data[hidden_frac][mode][race_type][batch][dataset][opt_name] = opt_results
    
    # Save the complete data structure
    output_file = OUTPUT_DIR / "playground_data.json"
    with open(output_file, 'w') as f:
        # Convert defaultdict to regular dict for JSON serialization
        json.dump(json.loads(json.dumps(all_data)), f, indent=2)
    
    print(f"\nGenerated: {output_file}")
    
    # Print summary
    print("\n=== Data Summary ===")
    for hidden_frac in sorted(all_data.keys()):
        print(f"\nHidden Fraction: {hidden_frac}")
        for mode in sorted(all_data[hidden_frac].keys()):
            print(f"  Mode: {mode}")
            for race_type in sorted(all_data[hidden_frac][mode].keys()):
                print(f"    Race Type: {race_type}")
                for batch in sorted(all_data[hidden_frac][mode][race_type].keys()):
                    datasets = list(all_data[hidden_frac][mode][race_type][batch].keys())
                    print(f"      Batch {batch}: {len(datasets)} datasets")
                    for dataset in sorted(datasets):
                        optimizers = list(all_data[hidden_frac][mode][race_type][batch][dataset].keys())
                        print(f"        {dataset}: {len(optimizers)} optimizers - {', '.join(sorted(optimizers)[:5])}...")
    
    # Check for missing data (hiddenfrac99, hard, open_race, batch20)
    print("\n=== Missing Data Check ===")
    missing_found = False
    try:
        test_data = all_data[0.99]["Hard"]["Open_Race"][20]
        if not test_data:
            print("Missing: hiddenfrac99, Hard mode, Open Race, Batch 20 - NO DATA")
            missing_found = True
        else:
            print("Found: hiddenfrac99, Hard mode, Open Race, Batch 20 - Has data for some datasets")
    except (KeyError, TypeError):
        print("Missing: hiddenfrac99, Hard mode, Open Race, Batch 20 - NO DATA")
        missing_found = True
    
    if not missing_found:
        # Check which datasets are missing batch 20
        test_data = all_data.get(0.99, {}).get("Hard", {}).get("Open_Race", {}).get(20, {})
        all_datasets = set()
        for batch in [1, 10]:
            batch_data = all_data.get(0.99, {}).get("Hard", {}).get("Open_Race", {}).get(batch, {})
            all_datasets.update(batch_data.keys())
        
        missing_datasets = all_datasets - set(test_data.keys())
        if missing_datasets:
            print(f"Missing batch 20 data for datasets: {', '.join(sorted(missing_datasets))}")
    
    return all_data


if __name__ == "__main__":
    print("Generating data files from Result_Official folder...\n")
    generate_data_files()
    print("\n✓ Data generation complete!")

