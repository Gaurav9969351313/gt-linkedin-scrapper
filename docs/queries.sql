select * from public.email_records;
select * from public.run_logs;
select * from public.jobs;


truncate table public.run_logs;
truncate table email_records;

create database prefect;
create database scraper_db;

=========================================================================================================
prefect deployment ls 

hr-email-dispatcher/hr-email-dispatcher               
scrape-single-job/scrape-job-1                  
scrape-single-job/scrape-job-2

docker exec scraper-worker prefect deployment run hr-email-dispatcher/hr-email-dispatcher

docker exec scraper-worker prefect deployment run scrape-single-job/scrape-job-1 -p '{"job_id": 1}'




