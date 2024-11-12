import boto3
import polars as pl
import sqlalchemy as sql
import df_cleaner as dc
import property_details_scraper as pds
import pyarrow as pa
import pyarrow.parquet as pq

from io import BytesIO
from datetime import timedelta, datetime

# Initialise AWS clients
session = boto3.Session(
    region_name="eu-west-2"
)

s3 = session.client("s3")

# Define the schedule
def lambda_handler(event, context):
    scraper = pds.DataScraper()
    cleaner = dc.DataCleaner()

    df_ce = cleaner.clean_central(scraper)
    df_sb = cleaner.clean_stow_bros(scraper)
    df_fx = cleaner.clean_foxtons(scraper)

    # Concatenate DataFrames (assuming df_sb and df_ce are Polars DataFrames)
    df = pl.concat([df_sb, df_ce, df_fx])

    # Select the necessary columns
    df = df.select([
        "update_date",
        "area",
        "num_beds",
        "cost_pcm",
        "address",
        "estate_agent",
        "description"
    ])

    # Generate the unique_id based on the description, cost_pcm, and area columns without casting to Int64
    df = df.with_columns(
        (pl.col("description") + pl.col("cost_pcm").cast(pl.Utf8) + pl.col("area").cast(pl.Utf8))
        .hash(10, 20, 30, 40)
        .alias("unique_id")  # Keep as u64 in Polars
    )

    # Convert the Polars DataFrame to a Pandas DataFrame
    df_pd = df.to_pandas()

    # Cast the unique_id column to string to avoid datatype issues with u64
    df_pd['unique_id'] = df_pd['unique_id'].astype(str)

    # Convert the df to a pyarrow table
    table = pa.Table.from_pandas(df_pd)
    
    # Create a buffer for the data to pass out of the script
    buffer = BytesIO()

    # Write the table to a parquet format
    pq.write_table(table, buffer)
    
    # Rewind the buffer
    buffer.seek(0)

    # Determine today's date to use as the filename
    current_date = datetime.now().date()
    formatted_date = current_date.strftime("%Y-%m-%d")
    
    # Specify output location and filename in s3
    bucket_name = "property-data-scraping"
    key = f"{formatted_date}"
    
    s3.upload_fileobj(buffer, bucket_name, key)
    
    return event, context

lambda_handler(None, None)