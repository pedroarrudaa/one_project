"""CSV processor for handling the visa AMA event data."""

import csv
import json
from typing import List, Dict, Any
from io import StringIO
import logging

logger = logging.getLogger(__name__)


class CSVProcessor:
    """Processor for CSV data from visa AMA events."""
    
    @staticmethod
    def parse_csv_file(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse CSV file and convert to list of profile dictionaries.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            List of profile dictionaries
        """
        profiles = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    profile = CSVProcessor._process_csv_row(row)
                    if profile:
                        profiles.append(profile)
                        
        except Exception as e:
            logger.error(f"Error processing CSV file {file_path}: {e}")
            raise
            
        return profiles
    
    @staticmethod
    def parse_csv_content(csv_content: str) -> List[Dict[str, Any]]:
        """
        Parse CSV content string and convert to list of profile dictionaries.
        
        Args:
            csv_content: CSV content as string
            
        Returns:
            List of profile dictionaries
        """
        profiles = []
        
        try:
            reader = csv.DictReader(StringIO(csv_content))
            
            for row in reader:
                profile = CSVProcessor._process_csv_row(row)
                if profile:
                    profiles.append(profile)
                    
        except Exception as e:
            logger.error(f"Error processing CSV content: {e}")
            raise
            
        return profiles
    
    @staticmethod
    def _process_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
        """
        Process a single CSV row into a profile dictionary.
        
        Args:
            row: Dictionary representing a CSV row
            
        Returns:
            Processed profile dictionary or None if invalid
        """
        try:
            # Extract and clean the data (handle BOM in CSV)
            api_id = row.get('api_id', '') or row.get('\ufeffapi_id', '')
            api_id = api_id.strip()
            name = row.get('name', '').strip()
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            email = row.get('email', '').strip()
            
            # Skip rows without essential data
            if not api_id or not name or not email:
                return None
            
            # Process optional fields
            linkedin_profile = row.get('what is your linkedin profile?', '').strip()
            works_in_ai = row.get('work/operate in ai?', '').strip()
            visa_journey_stage = row.get('where are you in your O-1/EB-1 application journey?', '').strip()
            questions_topics = row.get('This is an AMA panel, what question/topic will you like us to address?', '').strip()
            additional_info = row.get('anything else?', '').strip()
            
            # Clean up LinkedIn URL
            if linkedin_profile and not linkedin_profile.startswith('http'):
                if linkedin_profile.startswith('www.'):
                    linkedin_profile = 'https://' + linkedin_profile
                elif linkedin_profile.startswith('linkedin.com'):
                    linkedin_profile = 'https://' + linkedin_profile
                elif not linkedin_profile.startswith('N/A') and not linkedin_profile.startswith('n/a'):
                    linkedin_profile = 'https://' + linkedin_profile
            
            # Build profile dictionary
            profile = {
                'api_id': api_id,
                'name': name,
                'first_name': first_name if first_name else None,
                'last_name': last_name if last_name else None,
                'email': email,
                'linkedin_profile': linkedin_profile if linkedin_profile and linkedin_profile not in ['N/A', 'n/a', '-', ''] else None,
                'works_in_ai': works_in_ai if works_in_ai else None,
                'visa_journey_stage': visa_journey_stage if visa_journey_stage else None,
                'questions_topics': questions_topics if questions_topics and questions_topics not in ['N/A', 'n/a', '-', ''] else None,
                'additional_info': additional_info if additional_info and additional_info not in ['N/A', 'n/a', '-', ''] else None
            }
            
            return profile
            
        except Exception as e:
            logger.error(f"Error processing CSV row: {e}")
            return None
    
    @staticmethod
    def convert_to_batch_request(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert list of profiles to batch request format.
        
        Args:
            profiles: List of profile dictionaries
            
        Returns:
            Batch request dictionary
        """
        return {
            "profiles": profiles
        }
    
    @staticmethod
    def filter_ai_professionals(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter profiles to only include AI professionals.
        
        Args:
            profiles: List of profile dictionaries
            
        Returns:
            Filtered list of AI professional profiles
        """
        ai_profiles = []
        
        for profile in profiles:
            works_in_ai = (profile.get('works_in_ai') or '').lower()
            if works_in_ai in ['yes', 'y', 'true', '1']:
                ai_profiles.append(profile)
        
        return ai_profiles
    
    @staticmethod
    def get_visa_journey_statistics(profiles: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Get statistics about visa journey stages.
        
        Args:
            profiles: List of profile dictionaries
            
        Returns:
            Dictionary with statistics
        """
        stats = {}
        
        for profile in profiles:
            stage = profile.get('visa_journey_stage', 'Unknown')
            stats[stage] = stats.get(stage, 0) + 1
        
        return stats
    
    @staticmethod
    def validate_profiles(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate profiles and return validation summary.
        
        Args:
            profiles: List of profile dictionaries
            
        Returns:
            Validation summary dictionary
        """
        total_profiles = len(profiles)
        valid_profiles = 0
        invalid_profiles = []
        
        for i, profile in enumerate(profiles):
            is_valid = True
            errors = []
            
            # Check required fields
            if not profile.get('api_id'):
                errors.append("Missing api_id")
                is_valid = False
            
            if not profile.get('name'):
                errors.append("Missing name")
                is_valid = False
                
            if not profile.get('email'):
                errors.append("Missing email")
                is_valid = False
            
            if is_valid:
                valid_profiles += 1
            else:
                invalid_profiles.append({
                    'index': i,
                    'profile': profile,
                    'errors': errors
                })
        
        return {
            'total_profiles': total_profiles,
            'valid_profiles': valid_profiles,
            'invalid_profiles': len(invalid_profiles),
            'invalid_details': invalid_profiles[:10],  # Show first 10 invalid profiles
            'validation_rate': valid_profiles / total_profiles if total_profiles > 0 else 0
        }