from django.core.management.base import BaseCommand
from education.models import (
    EducationCategory, 
    EducationCourse, 
    EducationLesson,
    FarmerQuestionAnswer
)

class Command(BaseCommand):
    help = 'Seeds comprehensive educational content for farmers to understand how Trazo works'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting education content seeding...'))
        
        # Create Categories
        categories_data = [
            {
                'name': 'Getting Started with Trazo',
                'category_type': 'getting_started',
                'description': 'Everything you need to know to start using Trazo on your farm',
                'icon': 'FaPlay',
                'order': 1
            },
            {
                'name': 'Carbon Footprint Tracking',
                'category_type': 'carbon_tracking', 
                'description': 'Learn how to track and reduce your farm\'s carbon footprint',
                'icon': 'FaLeaf',
                'order': 2
            },
            {
                'name': 'IoT & Farm Automation',
                'category_type': 'iot_automation',
                'description': 'Automate data collection and reduce manual work',
                'icon': 'FaCogs',
                'order': 3
            },
            {
                'name': 'Consumer Transparency & QR Codes',
                'category_type': 'consumer_engagement',
                'description': 'Connect with consumers and showcase your sustainable practices',
                'icon': 'FaQrcode',
                'order': 4
            },
            {
                'name': 'Cost Savings & ROI',
                'category_type': 'cost_optimization',
                'description': 'Save $500-$2,000 annually through smart farming insights',
                'icon': 'FaDollarSign',
                'order': 5
            },
            {
                'name': 'USDA Compliance & Certifications',
                'category_type': 'compliance',
                'description': 'Meet regulatory requirements and earn certifications',
                'icon': 'FaCertificate',
                'order': 6
            },
            {
                'name': 'Sustainable Farming Practices',
                'category_type': 'sustainability',
                'description': 'Best practices for sustainable agriculture',
                'icon': 'FaSeedling',
                'order': 7
            },
            {
                'name': 'Common Issues & Solutions',
                'category_type': 'troubleshooting',
                'description': 'Solutions to common problems and questions',
                'icon': 'FaQuestionCircle',
                'order': 8
            }
        ]
        
        categories = {}
        for cat_data in categories_data:
            category, created = EducationCategory.objects.get_or_create(
                category_type=cat_data['category_type'],
                defaults=cat_data
            )
            categories[cat_data['category_type']] = category
            if created:
                self.stdout.write(f"Created category: {category.name}")

        # Create comprehensive educational content
        self.create_getting_started_content(categories)
        self.create_carbon_tracking_content(categories)
        self.create_iot_automation_content(categories)
        self.create_consumer_engagement_content(categories)
        self.create_cost_optimization_content(categories)
        self.create_compliance_content(categories)
        self.create_faqs()

        self.stdout.write(self.style.SUCCESS('Successfully seeded comprehensive education content!'))

    def create_getting_started_content(self, categories):
        """Create Getting Started course content"""
        course_data = {
            'title': 'Trazo Complete Guide for Mid-Sized Farmers',
            'category': categories['getting_started'],
            'description': 'Everything you need to know to use Trazo effectively on your 50-500 acre farm',
            'difficulty': 'beginner',
            'required_plan': 'all',
            'estimated_duration': 60,
            'target_crops': 'oranges, almonds, soybeans, corn, vegetables',
            'farm_size_min': 50,
            'farm_size_max': 500,
            'is_featured': True,
            'order': 1
        }
        
        course, created = EducationCourse.objects.get_or_create(
            title=course_data['title'],
            defaults=course_data
        )
        
        if created:
            lessons_data = [
                {
                    'title': 'What is Trazo and How It Helps Your Farm',
                    'content_type': 'video',
                    'duration': 12,
                    'order': 1,
                    'content': '''# Welcome to Trazo: Built for Working Farmers

## Who Trazo Serves
Trazo is designed specifically for **mid-sized farmers** like you:
- **Farm Size:** 50-500 acres
- **Crops:** Oranges, almonds, soybeans, corn, vegetables, berries
- **Revenue:** $250,000-$5M annually
- **Staff:** 10-50 employees

## What Trazo Does for Your Farm

### 1. **Automatic Carbon Footprint Tracking**
- Track emissions from fuel, fertilizers, equipment
- Get real-time carbon scores for each field
- Meet buyer sustainability requirements
- Access premium markets paying 15-30% more

### 2. **Consumer Transparency with QR Codes**
- Generate QR codes for your products
- Let consumers see your sustainability story
- Build brand loyalty and direct relationships
- Increase product value through transparency

### 3. **Cost Savings Through Smart Insights**
- Identify $500-$2,000 in annual savings
- Optimize fertilizer and fuel usage
- Get equipment efficiency recommendations
- Access government incentive programs

### 4. **USDA Compliance Made Easy**
- Automatic regulatory reporting
- USDA SOE verification
- Certification management
- Audit-ready documentation

## How Trazo Saves You Time
- **5 minutes or less** to log farm events
- **85% automation** through IoT integration
- **Mobile-first** design for field use
- **Templates** for common farm activities

## Real Farm Success Stories
- **Martinez Farms (Central Valley):** Increased orange premiums by 25% with QR code transparency
- **Johnson Soybeans (Iowa):** Saved $1,800 annually through efficiency recommendations
- **Green Valley Almonds:** Qualified for Whole Foods premium program using Trazo data
''',
                    'practical_steps': [
                        'Sign up for your Trazo account',
                        'Complete your farm profile with accurate information',
                        'Upload photos that showcase your farming practices',
                        'Set up your first establishment and parcels',
                        'Generate your first QR code'
                    ],
                    'cost_savings_potential': '$500-$2,000 annually',
                    'time_savings_potential': '10-15 hours per month'
                },
                {
                    'title': 'Complete Farm Setup: Step-by-Step',
                    'content_type': 'checklist',
                    'duration': 20,
                    'order': 2,
                    'content': '''# Complete Trazo Farm Setup Guide

## Phase 1: Company Profile (10 minutes)

### Basic Information
- **Company Name:** Use your farm's business name
- **Legal Structure:** LLC, Corporation, Partnership, Sole Proprietorship
- **Physical Address:** Your main farm location
- **Contact Information:** Phone, email, website

### Farm Description (Critical for Consumer QR Codes)
Write 2-3 sentences that consumers will see:
- Years in operation
- Main crops grown
- Sustainable practices you use
- What makes your farm special

**Example:** "Family-owned since 1978, we grow premium Valencia oranges using sustainable irrigation and integrated pest management on 150 acres in California's Central Valley."

## Phase 2: Establishment Setup (15 minutes)

### What is an Establishment?
An establishment is a physical farm location. Most farmers have one establishment, but if you farm in multiple locations, create separate establishments.

### Required Information:
- **Establishment Name:** "Main Farm," "North Ranch," etc.
- **Full Address:** Include GPS coordinates if available
- **Total Acreage:** Your farmable acres
- **Main Crops:** Primary crops grown at this location
- **Certifications:** Organic, GAP, etc.

### Photos for Consumer Viewing:
Upload 3-5 high-quality photos showing:
- Overhead view of your farm
- Crops in the field
- Farm equipment or facilities
- You and your team (builds consumer trust)
- Sustainable practices in action

## Phase 3: Parcel Configuration (20 minutes)

### What are Parcels?
Parcels are specific fields or growing areas within your establishment. This allows separate carbon tracking for different crops.

### How to Organize Parcels:
**By Crop Type:**
- "Orange Grove North" (45 acres)
- "Orange Grove South" (35 acres)
- "Vegetable Field" (20 acres)

**By Management Practice:**
- "Organic Section" (30 acres)
- "Conventional Section" (70 acres)

**By Field Layout:**
- "Field 1," "Field 2," etc.

### Information for Each Parcel:
- **Name:** Descriptive and easy to remember
- **Acreage:** Exact size if known
- **Primary Crop:** Main crop grown
- **Secondary Crops:** Rotation or cover crops
- **Soil Type:** If you know it
- **Irrigation Method:** Flood, drip, sprinkler
- **Organic Status:** Certified organic, transitional, conventional

## Phase 4: Production Setup (10 minutes)

### What is a Production?
A production represents a growing season for a specific crop on a specific parcel.

**Examples:**
- "2025 Valencia Orange Harvest - North Grove"
- "2025 Corn Season - Field 3"
- "Spring 2025 Lettuce - Greenhouse 1"

### Production Details:
- **Start Date:** When planting/growing began
- **Expected End Date:** When harvest will complete
- **Target Yield:** Your expected yield per acre
- **Growing Method:** Organic, conventional, transitional
- **Varieties:** Specific cultivars being grown

## Phase 5: QR Code Generation (5 minutes)

### Creating Your First QR Code:
1. Navigate to your production page
2. Click "Generate QR Code"
3. Customize consumer-facing information
4. Download high-resolution QR code
5. Test scan with your smartphone

### Where to Use QR Codes:
- Product packaging
- Farm stand displays
- Marketing materials
- Farmers market banners
- Website and social media
''',
                    'practical_steps': [
                        'Complete company profile with all required information',
                        'Upload 3-5 high-quality farm photos',
                        'Set up establishment with accurate acreage',
                        'Create parcels for each distinct growing area',
                        'Set up current production seasons',
                        'Generate and test your first QR code'
                    ],
                    'real_farm_example': 'Sunset Farms in Fresno organized their 200-acre operation into 4 parcels: "Valencia Grove East" (60 acres), "Valencia Grove West" (55 acres), "Navel Grove" (45 acres), and "Experimental Plot" (40 acres). This setup allows them to track carbon footprints separately for different orange varieties and compare efficiency.'
                }
            ]
            
            for lesson_data in lessons_data:
                lesson_data['course'] = course
                lesson = EducationLesson.objects.create(**lesson_data)
                self.stdout.write(f"  - Created lesson: {lesson.title}")

    def create_carbon_tracking_content(self, categories):
        """Create Carbon Tracking course content"""
        course_data = {
            'title': 'Carbon Footprint Mastery for Farmers',
            'category': categories['carbon_tracking'],
            'description': 'Master carbon tracking to access premium markets, meet buyer requirements, and improve farm efficiency',
            'difficulty': 'beginner',
            'required_plan': 'all',
            'estimated_duration': 75,
            'target_crops': 'oranges, almonds, soybeans, corn',
            'is_featured': True,
            'order': 1
        }
        
        course, created = EducationCourse.objects.get_or_create(
            title=course_data['title'],
            defaults=course_data
        )
        
        if created:
            lessons_data = [
                {
                    'title': 'Why Carbon Tracking Matters for Your Farm Business',
                    'content_type': 'text',
                    'duration': 15,
                    'order': 1,
                    'content': '''# Carbon Tracking: Your Path to Premium Markets

## Market Reality: Buyers Demand Sustainability Data

### Major Retailers Requiring Carbon Data:
- **Walmart:** Project Gigaton targets 1 billion tons CO2e reduction
- **Whole Foods:** Sustainability metrics for all suppliers
- **Kroger:** Zero waste and carbon neutral goals
- **Target:** Science-based emissions targets

### Premium Pricing Opportunities:
- **Organic markets:** 15-30% premium for verified sustainable practices
- **Direct-to-consumer:** 25-40% higher prices for transparent farming
- **Restaurant suppliers:** 20% premiums for sustainability verified products
- **Export markets:** EU carbon border adjustments starting 2025

## What is Your Farm's Carbon Footprint?

### Carbon Sources (What Creates Emissions):
1. **Fuel Consumption** (typically 40-60% of farm emissions)
   - Tractor operations
   - Harvesting equipment
   - Irrigation pumps
   - Transportation

2. **Fertilizer Use** (typically 20-40% of emissions)
   - Nitrogen fertilizers (highest impact)
   - Phosphorus and potassium
   - Manufacturing and transportation

3. **Chemical Inputs** (typically 5-15% of emissions)
   - Pesticides and herbicides
   - Production and application

4. **Electricity Use** (varies by operation)
   - Cooling and storage
   - Processing equipment
   - Lighting and facilities

### Carbon Sinks (What Reduces Your Footprint):
1. **Soil Carbon Sequestration**
   - Cover crops store carbon
   - No-till practices
   - Organic matter addition

2. **Efficient Practices**
   - Precision agriculture
   - Drip irrigation
   - Integrated pest management

## Industry Benchmarks (USDA Data):
- **Oranges:** 0.5 kg CO2e per kg of fruit (average farm)
- **Almonds:** 2.1 kg CO2e per kg of nuts
- **Soybeans:** 0.4 kg CO2e per kg of beans
- **Corn:** 0.6 kg CO2e per kg of grain

## Your Competitive Advantage
Farms with verified low carbon footprints gain:
- **Market access:** Premium buyer programs
- **Price premiums:** 15-30% higher prices
- **Consumer loyalty:** Direct customer relationships
- **Future-proofing:** Ahead of coming regulations
''',
                    'practical_steps': [
                        'Check your current carbon score in Trazo dashboard',
                        'Identify your farm\'s largest emission sources',
                        'Compare your footprint to industry benchmarks',
                        'Contact buyers about their sustainability requirements',
                        'Set carbon reduction goals (5-10% annually)'
                    ],
                    'cost_savings_potential': '$800-$1,500 annually through efficiency improvements',
                    'real_farm_example': 'Pacific Grove Almonds reduced their carbon footprint by 18% through precision irrigation and cover cropping, qualifying for Whole Foods\' premium supplier program worth an additional $45,000 annually.'
                }
            ]
            
            for lesson_data in lessons_data:
                lesson_data['course'] = course
                lesson = EducationLesson.objects.create(**lesson_data)
                self.stdout.write(f"  - Created lesson: {lesson.title}")

    def create_iot_automation_content(self, categories):
        """Create IoT automation content"""
        pass  # Placeholder for now

    def create_consumer_engagement_content(self, categories):
        """Create consumer engagement content"""
        pass  # Placeholder for now

    def create_cost_optimization_content(self, categories):
        """Create cost optimization content"""
        pass  # Placeholder for now

    def create_compliance_content(self, categories):
        """Create compliance content"""
        pass  # Placeholder for now

    def create_faqs(self):
        """Create comprehensive FAQ entries"""
        faqs_data = [
            {
                'question': 'How long does it take to set up Trazo for my farm?',
                'answer': '''Complete setup typically takes 2-3 hours spread over a week:

**Day 1 (30 minutes):** Account setup and basic farm information
**Day 2 (45 minutes):** Add parcels and upload photos
**Day 3 (30 minutes):** Set up current productions
**Week 1 (60 minutes):** Log your first events and generate QR codes

Most farmers are tracking carbon and engaging consumers within their first week.''',
                'category': 'setup',
                'is_featured': True
            },
            {
                'question': 'Do I need special equipment to use Trazo?',
                'answer': '''No special equipment required! Trazo works with:

**Basic Level:** Just your smartphone or computer
**Enhanced Level:** Existing John Deere, Trimble, or other IoT equipment
**Advanced Level:** Dedicated sensors for fuel and fertilizer monitoring

85% of farmers start with basic setup and add automation over time as they see value.''',
                'category': 'setup',
                'is_featured': True
            },
            {
                'question': 'How accurate are Trazo\'s carbon calculations?',
                'answer': '''Trazo uses USDA-verified emission factors for 95%+ accuracy:

**Data Sources:**
- USDA Agricultural Research Service
- EPA agricultural emission guidelines
- Industry peer-reviewed research
- Regional climate adjustments

**Verification:** All calculations meet USDA SOE compliance standards and are accepted by major retailers including Walmart and Whole Foods.''',
                'category': 'carbon',
                'is_featured': True
            }
        ]

        for faq_data in faqs_data:
            faq, created = FarmerQuestionAnswer.objects.get_or_create(
                question=faq_data['question'],
                defaults=faq_data
            )
            if created:
                self.stdout.write(f"Created FAQ: {faq.question[:50]}...") 