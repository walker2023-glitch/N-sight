import math

def CalAveCropYield(years):
    total_yield = 0
    for i in range(years):
        total_yield += float(input(f"What was the crop yield for year {i+1}: "))
    return total_yield / years

def CalPrecipitation(rainfall_inch):
    try:
        inches = float(rainfall_inch)
        if inches < 18:
            return 2.4
        elif 18 <= inches < 21:
            return 2.5
        elif 21 <= inches < 24:
            return 2.7
        elif 24 <= inches < 28:
            return 2.9
        else:
            return 3.1
    except ValueError:
        print("Invalid rainfall entered, defaulting to 2.4")
        return 2.4

def calMineralisable(organic_matter):
    # Round to avoid floating point mismatch bugs
    om = round(float(organic_matter), 1)
    
    if om <= 1.0:
        return -20
    elif om >= 3.0:
        return -60
    else:
        # Calculates the step mathematically instead of 20 match cases!
        # Every 0.1 increase adds -2 to the nitrogen credit
        return -20 - int((om - 1.0) * 20) * 2

def soilNitrate():
    print("\n--- Soil Nitrate Test (PPM) ---")
    # 3.5 is the conversion factor from PPM to lbs/acre for a 12-inch core
    ppm0_12 = float(input("Total N PPM for 0-12 inches: ")) * 3.5
    ppm12_24 = float(input("Total N PPM for 12-24 inches: ")) * 3.5
    ppm24_36 = float(input("Total N PPM for 24-36 inches: ")) * 3.5
    return ppm0_12 + ppm12_24 + ppm24_36

def determinePreviousCereal(cereal_residue):
    # Cereal straw ties up nitrogen (Positive value means you must ADD more N)
    mapping = {0: 0, 0.5: 7.5, 1: 15, 2: 30, 2.5: 37.5, 3: 45, 3.5: 50}
    return mapping.get(cereal_residue, 0)

def determinePreviousLegumes(legume_residue):
    # Legumes fix nitrogen (Negative value means it SUBTRACTS from needed N)
    mapping = {0: 0, 1: -8, 1.5: -23, 2: -30, 3: -45, 3.5: -60}
    return mapping.get(legume_residue, 0)


# --- MAIN PROGRAM ---
print("=== Nitrogen Fertilizer Recommendation Calculator ===\n")

years = int(input("Enter how many years of history to average: "))
aveCropYield = CalAveCropYield(years)
print(f"Average Crop Yield Potential: {aveCropYield:.2f} bu/acre\n")

rain_input = input("Enter precipitation total for the last year (inches): ")
precipitation_factor = CalPrecipitation(rain_input)

BLR = aveCropYield * precipitation_factor
print(f"Base Nitrogen Requirement (BLR): {BLR:.2f} lbs/acre\n")

om_input = input("How much Organic Matter % (or PPA) is in the soil? ")
mini_credit = calMineralisable(om_input)

# Get existing soil nitrate
SN_credit = soilNitrate()

# Fix the flipped logic bug
cl_question = input("\nWas the previous crop a type of legume? (Y/N): ").strip().upper()
if cl_question == "Y":
    residue = float(input("Enter legume residue level (0 to 3.5): "))
    residue_credit = determinePreviousLegumes(residue)
else:
    residue = float(input("Enter cereal residue level (0 to 3.5): "))
    residue_credit = determinePreviousCereal(residue)

# FINAL CALCULATION (Including SN_credit now!)
# Note: because mini_credit and legume residue_credit are already negative numbers, 
# we add them to reduce the final total. We subtract the SN_credit because it's a positive number.
RecommendedRateOfNitrogen = BLR + float(mini_credit) + float(residue_credit) - SN_credit
RecommendedRateOfUrea = RecommendedRateOfNitrogen/0.46;
# Ensure we don't recommend a negative amount of fertilizer
if RecommendedRateOfNitrogen < 0:
    RecommendedRateOfNitrogen = 0
price = float(input("Enter the current price of Urea:"))
costEst = RecommendedRateOfUrea * price / 2205

print("\n==============================================")
print(f"Recommended Nitrogen to Apply: {RecommendedRateOfNitrogen:.2f} lbs/acre")
print("==============================================")
print(f"Recommended Urea to Apply: {RecommendedRateOfUrea:.2f} lbs/acre")
print("\n==============================================")
print(f"Estimated cost to Apply: {costEst:.2f}$ metric-ton/acre")
print("\n==============================================")