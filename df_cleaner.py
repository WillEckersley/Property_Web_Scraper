import polars as pl
import property_details_scraper as pds
from datetime import datetime

class DataCleaner:

    def clean_central(self, scraper):
        
        df_dict = scraper.scrape_central()
        
        # Create a dataframe from the dictionary and perform all transformations in a single chain
        df_ce = (
            pl.DataFrame(df_dict)
            .with_columns([
                # Reformat cost column
                pl.col("cost")
                .str.replace("PCM, Fees Apply", "")
                .str.replace("£", "")
                .str.strip_chars(" ")
                .str.replace(",", "")
                .cast(pl.Int64)
                .alias("cost_sterling"),

                # Cast num_beds and num_baths columns
                pl.col("num_beds").cast(pl.Int32),
                pl.col("num_baths").cast(pl.Int32),

                # Create area column using generator
            
                pl.col("address").map_elements(
                    lambda address_list: next(
                        (area for area in ["Wanstead", "Walthamstow", "Leytonstone", "Leyton", "Chingford", "London"]  
                        if any(area in part for part in address_list)), None), return_dtype=str
                ).alias("area"),

                # Record the date the data was added
                pl.lit(datetime.now().strftime("%Y-%m-%d"))
                .str.to_date(format="%Y-%m-%d")
                .alias("update_date"),

                # Add the estate agent column
                pl.lit("Central").alias("estate_agent")
            ])
            # Select and rename the columns in one step
            .select([
                "update_date",
                "area",
                "num_beds",
                #"num_baths", - removed as data unavailable for other estate agents
                "cost_sterling",
                "address",
                "estate_agent",
                "description"
            ])
        ).rename({"cost_sterling" : "cost_pcm"})

        return df_ce
    
    def clean_stow_bros(self, scraper):
        df_dict = scraper.scrape_stow_bros()

        df = pl.DataFrame(df_dict)

        df = df.with_columns(
            pl.col("price")
            .str.replace(" ", "")
            .str.replace("pcm", "")
            .str.replace("£", "")
            .str.replace(",", "")
            .cast(pl.Int64),
            
            pl.col("address")
            .str.split(",")
            .list.get(-1)
            .str.replace(" ", "")
            .alias("area"),

            pl.col("address")
            .str.split(","),

            pl.lit("Stow Bros").alias("estate_agent"),
            
            # Record the date the data was added
            pl.lit(datetime.now().strftime("%Y-%m-%d"))
            .str.to_date(format="%Y-%m-%d")
            .alias("update_date"),

            pl.lit(0).alias("num_beds")

        ).rename({"price" : "cost_pcm"})

        text_numbers_list = ["One", "Two", "Three", "Four", "Studio"]
        text_number_map = {number : count for number, count in zip(text_numbers_list, range(1, len(text_numbers_list) + 1))}
        text_number_map["Studio"] = 1

        for number in text_numbers_list:
            df = df.with_columns(
                pl.when(pl.col("description").str.contains(number))
                .then(
                    pl.lit(text_number_map[number])
                )
                .otherwise(pl.col("num_beds")) 
                .alias("num_beds")
            )

        df_sb = df.with_columns(
            num_beds=pl.when(pl.col("num_beds") == 0)
            .then(pl.lit(None))
            .otherwise(pl.col("num_beds"))
        ).select([
            "update_date",
            "area",
            "num_beds",
            "cost_pcm",
            "address",
            "estate_agent",
            "description"
        ])

        return df_sb
    
    def clean_foxtons(self, scraper):
        df_dict = scraper.scrape_foxtons()

        # Preprocess the 'address' column
        addresses = df_dict["address"]

        # Split the addresses into lists
        address_lists = [address.split(",") for address in addresses]

        # Extract the area from the address lists
        areas = []
        for addr_list in address_lists:
            if len(addr_list) >= 2:
                area = addr_list[1].strip()
            else:
                area = None
            areas.append(area)

        # Update the df_dict with the processed 'address' and 'area'
        df_dict["address"] = address_lists
        df_dict["area"] = areas

        # Create the DataFrame
        df = pl.DataFrame(df_dict)

        df_fx = df.with_columns([
            # Extract the numeric part from cost_pcm and alias the column
            (
                pl.col("cost_pcm")
                .str.split(" ")
                .list.get(2, null_on_oob=True)
                .str.replace(r"£|pcm", "")
                .str.split(".")
                .list.get(0)
                .str.replace(",", "")
                .cast(int)
            ),
            
            # Extract number of beds from num_beds column using refined regex
            (
                pl.col("num_beds")
                .cast(pl.Int32)
                .alias("num_beds")
            ),
            
            # Add constant estate agent and alias the column
            pl.lit("Foxtons").alias("estate_agent"),
            
            # Record the date the data was added and alias the column
            (
                pl.lit(datetime.now().strftime("%Y-%m-%d"))
                .str.strptime(pl.Date, "%Y-%m-%d")
                .alias("update_date")
            ),
            
            # Description is set to None and alias the column
            pl.lit(None).alias("description")
        ])

        # Select the required columns
        df_fx = df_fx.select([
            "update_date",
            "area",
            "num_beds",
            "cost_pcm",
            "address",
            "estate_agent",
            "description"
        ])
    
        return df_fx
    
if __name__ == "__main__":
    scraper = pds.DataScraper(driver_path="/Users/willeckersley/projects/Repositories/Central_estates_web_scraper/chromedriver-mac-x64/chromedriver")
    cleaner = DataCleaner()
    central = cleaner.clean_central(scraper)
    stow = cleaner.clean_stow_bros(scraper)
    fox = cleaner.clean_foxtons(scraper)

    print(central)
    print(stow)
    print(fox)