import csv
from collections import defaultdict, Counter

# Data structure: {ECO_code: {"White": [games, wins, draws, losses], "Black": [games, wins, draws, losses]}}
eco_performance = defaultdict(lambda: {"White": [0,0,0,0], "Black": [0,0,0,0]})

for game in games_data:
    eco = game.get("ECO","")
    white = game.get("White","")
    black = game.get("Black","")
    result = game.get("Result","")

    if white == "IlliquidAsset":
        # White perspective
        eco_performance[eco]["White"][0] += 1  # games
        if result == "1-0":
            eco_performance[eco]["White"][1] += 1  # wins
        elif result == "1/2-1/2":
            eco_performance[eco]["White"][2] += 1  # draws
        elif result == "0-1":
            eco_performance[eco]["White"][3] += 1  # losses

    elif black == "IlliquidAsset":
        # Black perspective
        eco_performance[eco]["Black"][0] += 1  # games
        if result == "0-1":
            eco_performance[eco]["Black"][1] += 1  # wins
        elif result == "1/2-1/2":
            eco_performance[eco]["Black"][2] += 1  # draws
        elif result == "1-0":
            eco_performance[eco]["Black"][3] += 1  # losses

csv_filename = "eco_performance.csv"

# Create CSV
with open(csv_filename, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    # Header
    writer.writerow([
        "ECO",
        "White_Games", "White_Wins", "White_Draws", "White_Losses",
        "Black_Games", "Black_Wins", "Black_Draws", "Black_Losses",
        "Total_Games"
    ])

    for eco_code, data in sorted(eco_performance.items()):
        w_games, w_wins, w_draws, w_losses = data["White"]
        b_games, b_wins, b_draws, b_losses = data["Black"]
        total = w_games + b_games
        writer.writerow([
            eco_code,
            w_games, w_wins, w_draws, w_losses,
            b_games, b_wins, b_draws, b_losses,
            total
        ])

print(f"CSV created: {csv_filename}")