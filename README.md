# London Rental Property ML Data Pipeline

<p align="center">
    <img src="https://github.com/WillEckersley/Property_Web_Scraper/blob/main/readme_images/HEADER.webp" alt="Pinterest Logo">
</p>

### §1 Overview:

This project uses an cloud-based serverless webscraping application to extract and clean London rental property data from several internet sites. The scraped data is loaded into a cloud-based datalake where it can be queried using SQL in a lakehouse-style
layer. This lakehouse layer isued to perform an ELT on the scraped date. Initially it is processed extracted and loaded into a raw 'bronze' table. This 'bronze' data is then transformed within the lakehouse-style environment using a bronze-silver-gold pattern of further cleaning (in the silver table) and aggregation (in the gold layer). The purpose of this is to use 
the gold table as a data source for a basic ML model which can be used to predict price changes across areas and property sizes.

The purpose of this project was to develop new skills that bridge Data Engineering, DevOps and MLOps workflows with a view to demonstrating new capability with MLOps. For instance I learned webscraping, CI/CD principles and ML pipeline principles. To that extent, the 
project continues to be a work in progress as the gold table has not been integrated into the model. Future developements will centre around building out the ML model itself, CI/CD features for accurate model deployment as well as the introduction of monitoring systems to ensure proper maintence of the entire ML pipeline - WATCH THIS SPACE!
Nonetheless, for now the ETL + ELT pipelines (and associated CI/CD) underlaying the model are fully deployed and running on a daily loaded schedule. As such I have chosen to show off this part of the overall pipeline now as it represnts signficant progress towards the finished project.

### §2 Pipeline Architechture:

See below for the basic architechture of the data pipeline:

![pipeline architechure](https://github.com/WillEckersley/Property_Web_Scraper/blob/main/readme_images/property_ml_pipeline.svg)

### §3 ETL - Phase One:

The ETL portion of the data pipeline utilises an object-oriented application design pattern to extract property data from the internet using Selenium and load it into the AWS S3 datalake in parquet format. Parquet was chosen for its efficiency and compatibility with a range of advanced systems and software. Between these steps Polars is used to perform basic basic 
formatting of the data. The application is hosted on AWS. There it is stored as Dockerised application in AWS ECR and defined as a task using ECS Fargate. It is scheduled to be run on a daily basis using EventBridge Scheduler. 

#### 3.1 Extraction:

Data extraction is is managed by the property_details_scraper.py file. This file uses a class - 'DataScraper' - to objectify three separate data scrapers: one for each of the estate agents currently targetted for data extraction. This script leverages Selenium to 
extract the relevant raw data from a range of different sources online. This raw string data is then passed in the main.py file into cleaning functions described bellow.

#### 3.2 Transformation:

The raw scraped data is given a first parse in the df_cleaner.py file. This file leverages Polars for rapid data manipulation and effective formatting. Cleaning functions objectified in a 'DataCleaner' class analogous to the scraping functions in DataCleaner individually handle the return of the dataframes generated from the cleaning file. 

#### 3.4 Loading: 

The data cleaned in the cleaning file is then consolidated into a single parquet file, a unique Id added and the file exported to AWS S3 in main.py. The files are exported to a bucket with the following structure: 

```
property-data-scraping/date={ingestion_date}/{ingestion_date}
```

![s3](https://github.com/WillEckersley/Property_Web_Scraper/blob/main/readme_images/S3.png)

This folder structure facilitates high levels of data availability through the use of partition projection in the AWS Athena lakehouse-style platform. This feature allows auto-partitioning of data based on folders named with a date/time structure (see more below).  

### §4 ELT - Phase Two:

Although the data is successfully loaded into the S3 datalake at the completion of phase 1, the data is clearly insufficient for use in an ML model. Webscraping can often produce anomolous or unexpected results and so the choice was made to perform a further ELT on the raw ingested data stored in S3 in order to effectively prepare the data for deployment in an ML prediction model. 

#### 4.1 Extraction and Loading:

In this step data is extracted from the data lake into a bronze table 'rental_property_data_scraping_bronze' in the AWS Athena using a CREATE TABLE statement based partitially off a Glue Crawler table which was used to build the table on the first parse:  
```
CREATE EXTERNAL TABLE `rental_property_data_scraping_bronze`(
  `update_date` timestamp, 
  `area` string, 
  `num_beds` double, 
  `cost_pcm` double, 
  `address` array<string>, 
  `estate_agent` string, 
  `description` string, 
  `unique_id` string)
PARTITIONED BY ( 
  `date` string)
ROW FORMAT SERDE 
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION
  's3://property-data-scraping/'
TBLPROPERTIES (
  'partition_filtering.enabled'='true', 
  'projection.date.format'='yyyy-MM-dd', 
  'projection.date.interval'='1', 
  'projection.date.interval.unit'='DAYS', 
  'projection.date.range'='2023-01-01,2033-12-31', 
  'projection.date.type'='date', 
  'projection.enabled'='true', 
  'storage.location.template'='s3://property-data-scraping/date=${date}/', 
  'transient_lastDdlTime'='1732988748'
);
```
Here, as mentioned above, in the TBLPROPERTIES (table properties) partition projection on the 'date' property is used for efficient extraction and loading. This removes the need to run either of the 
below commands: 
```
ALTER TABLE ADD IF NOT EXISTS PARTITION ({partition_name})

--OR

MSCK REPAIR TABLE {table_name}
```
Either of these methods must be used where an alternative (auto-)parititioning method is not employed. This effectively allows the data to be auto-loaded while also preserving useful information in the source table (ingestion date).

#### 4.2 Transformation:

Transformation of the data in the raw bronze table is then first performed using a silver table: 'rental_property_data_scraping_silver'. This table exists as a view within AWS Athena which automatically updates based on the partitions added in the bronze table. It's 
primary function is to remove duplicates/nulls/unwanted data from the daily loads and to reformat the datatypes into more suitable formats: 
```
CREATE OR REPLACE VIEW "rental_property_data_scraping_silver" AS 
SELECT DISTINCT
  CAST(date AS DATE) ingestion_date
, area
, CAST(num_beds AS INT) num_beds
, CAST(cost_pcm AS INT) cost_pcm
, ARRAY_JOIN(address, ',') address
, estate_agent
, description
, unique_id
FROM
  rental_property_data_scraping_bronze
WHERE ((num_beds IS NOT NULL) AND (area IS NOT NULL) AND (area <> 'London') AND (area <> 'LONDON'))
```
Finally, the data is aggregated in a gold table. This table also builds out a couple of engineered features to improve the model accuracy during training and deployment.  

![gold table](https://github.com/WillEckersley/Property_Web_Scraper/blob/main/readme_images/gold_table.png)

### §5 ...

WATCH THIS SPACE FOR FURTHER DEVELOPMENTS COMING SOON! 







