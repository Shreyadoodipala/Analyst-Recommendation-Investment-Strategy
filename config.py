import dotenv
import os

# Load environment variables from .env file
dotenv.load_dotenv()

# Environment variables
PROJECT_ID = os.getenv('PROJECT_ID')
DATASET_ID = os.getenv('DATASET_ID')
REC_TABLE_ID = os.getenv('REC_TABLE_ID')

ORIGINAL_DATASET = os.getenv('ORIGINAL_DATASET')
ORIGINAL_TABLE = os.getenv('ORIGINAL_TABLE')

FRED_API_KEY = os.getenv('FRED_API_KEY')