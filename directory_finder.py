<<<<<<< HEAD
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from playwright.sync_api import sync_playwright
from ai_extractor import extract_missing_contact_fields_with_ai
from config import USER_AGENT, TIMEOUT
import html
import asyncio
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor


ZOHO_DIRECTORY_URL = "https://www.zoho.com/partners/find-zoho-partner.html"
MICROSOFT_DIRECTORY_URL = "https://microsoftpartners.microsoft.com/abs/Partner-Directories/"
MICROSOFT_PARTNER_URL = "https://marketplace.microsoft.com/en-us/marketplace/partner-dir"


def fetch_page(url):
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.text


def parse_page(html):
    return BeautifulSoup(html, "html.parser")


def clean_lines(text):
    return [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]


def clean_location(location):
    location = location.replace("\xa0", " ")
    location = re.sub(r"([a-z])India", r"\1, India", location)
    location = re.sub(r"([A-Z][a-z]+)India", r"\1, India", location)
    return " ".join(location.split()).strip()


def extract_email(text):
    emails = re.findall(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        text
    )
    return emails[0] if emails else ""


def extract_phone(text):
    phones = re.findall(r"\+?\d[\d\s().-]{7,}\d", text)
    return phones[0].strip() if phones else ""

def is_company_website(url):
    if not url or not url.startswith("http"):
        return False

    blocked_domains = [
        "zoho.com",
        "zohocorp.com",
        "microsoft.com",
        "microsoftpartners.microsoft.com",
        "marketplace.microsoft.com",
        "appsource.microsoft.com",
        "microsoftcloudpartner.eventbuilder.com",
        "eventbuilder.com",
        "aka.ms",
        "learn.microsoft.com",
        "support.microsoft.com",
        "go.microsoft.com",
        "cdn-dynmedia-1.microsoft.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "instagram.com",
        "linkedin.com",
        "youtube-nocookie.com"
    ]

    domain = urlparse(url).netloc.lower().replace("www.", "")

    return not any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in blocked_domains
    )


def extract_company_website_from_links(base_url, links):
    for href in links:
        if not href:
            continue

        full_url = urljoin(base_url, href).split("#")[0].strip()

        if is_company_website(full_url):
            return full_url.rstrip("/")

    return ""


def extract_company_website_from_html(html, base_url):
    soup = parse_page(html)
    hrefs = [link.get("href", "") for link in soup.find_all("a")]
    return extract_company_website_from_links(base_url, hrefs)


def remove_duplicate_partners(partners):
    unique = []
    seen = set()

    for partner in partners:
        key = (
            partner.get("ecosystem", "").lower(),
            partner.get("company_name", "").lower(),
            partner.get("website", "").lower(),
            partner.get("partner_profile_url", "").lower()
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(partner)

    return unique


def remove_duplicate_directories(directories):
    unique = []
    seen = set()

    for directory in directories:
        key = directory["url"].lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(directory)

    return unique


def build_zoho_profile_url(partner_id):
    if not partner_id:
        return ""

    return f"https://www.zoho.com/partners/find-partner-profile.html?partnerid={partner_id}"

def clean_url(url):
    if not url:
        return ""

    url = url.strip()

    if url == "#":
        return ""

    return url.split("?")[0].split("#")[0].rstrip("/")


def extract_email_from_href(href):
    if not href:
        return ""

    href = href.strip()

    if href.lower().startswith("mailto:"):
        email = href.split(":", 1)[1].split("?")[0].strip()
        return email if extract_email(email) else ""

    return extract_email(href)


def extract_phone_from_href(href):
    if not href:
        return ""

    href = href.strip()

    if href.lower().startswith("tel:"):
        return href.split(":", 1)[1].split("?")[0].strip()

    return ""


def is_partner_contact_email(email):
    if not email:
        return False

    domain = email.split("@")[-1].strip().lower()

    blocked_domains = {
        "microsoft.com",
        "zohocorp.com",
        "zoho.com"
    }

    return domain not in blocked_domains


def is_valid_linkedin_url(url):
    url = clean_url(url)

    if not url:
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    return domain.endswith("linkedin.com")


async def extract_zoho_profile_details_async(context, profile_url):
    details = {
        "website": "",
        "linkedin": "",
        "phone": "",
        "contact_email": ""
    }

    if not profile_url:
        return profile_url, details

    page = await context.new_page()

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_selector(".zwc-details-common", timeout=12000)
        except Exception:
            pass

        try:
            website = await page.locator("a.zwc-pr-weblink").first.get_attribute(
                "href",
                timeout=3000
            )
            website = clean_url(website)

            if is_company_website(website):
                details["website"] = website
        except Exception:
            pass

        try:
            linkedin = await page.locator("a.zwc-pr-linkedin").first.get_attribute(
                "href",
                timeout=3000
            )
            linkedin = clean_url(linkedin)

            if is_valid_linkedin_url(linkedin):
                details["linkedin"] = linkedin
        except Exception:
            pass

        if not details["linkedin"]:
            hrefs = await page.locator("a").evaluate_all(
                "links => links.map(link => link.href || link.getAttribute('href') || '')"
            )

            for href in hrefs:
                href = clean_url(href)

                if is_valid_linkedin_url(href):
                    details["linkedin"] = href
                    break

        body_text = await page.locator("body").inner_text(timeout=5000)
        details["phone"] = extract_phone(body_text)
        details["contact_email"] = extract_email(body_text)

    except Exception as error:
        details["profile_error"] = str(error)[:200]

    finally:
        await page.close()

    return profile_url, details





async def fetch_zoho_profiles_fast(profile_urls, concurrency=4):
    results = {}
    profile_urls = list(dict.fromkeys([url for url in profile_urls if url]))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()

        async def block_heavy_assets(route):
            resource_type = route.request.resource_type

            if resource_type in {"image", "media", "font"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", block_heavy_assets)

        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(profile_url):
            async with semaphore:
                return await extract_zoho_profile_details_async(context, profile_url)

        tasks = [run_one(url) for url in profile_urls]

        for task in asyncio.as_completed(tasks):
            profile_url, details = await task
            results[profile_url] = details

        await browser.close()

    return results


def get_zoho_profiles_fast(profile_urls, concurrency=4):
    def runner():
        return asyncio.run(
            fetch_zoho_profiles_fast(profile_urls, concurrency=concurrency)
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(runner).result()



async def fetch_zoho_profiles_fast(profile_urls, concurrency=8):
    results = {}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()

        async def block_heavy_assets(route):
            resource_type = route.request.resource_type

            if resource_type in {"image", "media", "font", "stylesheet"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", block_heavy_assets)

        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(profile_url):
            async with semaphore:
                return await extract_zoho_profile_details_async(context, profile_url)

        tasks = [
            run_one(profile_url)
            for profile_url in profile_urls
            if profile_url
        ]

        for task in asyncio.as_completed(tasks):
            profile_url, details = await task
            results[profile_url] = details

        await browser.close()

    return results


def get_zoho_profiles_fast(profile_urls, concurrency=8):
    return asyncio.run(fetch_zoho_profiles_fast(profile_urls, concurrency=concurrency))


def scrape_zoho_partners():
    partners = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(ZOHO_DIRECTORY_URL, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_selector(".res-partner-details", timeout=30000)
        except Exception:
            page.wait_for_timeout(8000)

        cards = page.locator(".res-partner-details").all()
        raw_partners = []

        for card in cards:
            try:
                card_data = card.evaluate("""
                    element => {
                        const li = element.closest("li") || element;

                        return {
                            company_name: element.querySelector(".res-name")?.innerText?.trim() || "",
                            location: element.querySelector(".zwc-cd-address")?.innerText?.trim() || "",
                            email: element.querySelector(".zwc-cd-mailid a")?.innerText?.trim() || "",
                            services_offered: li.getAttribute("data-practice") || "",
                            tier: li.getAttribute("data-tier") || "",
                            categories: li.getAttribute("data-categories") || "",
                            industry: li.getAttribute("data-industry") || "",
                            rating: li.getAttribute("data-avg-rating") || "",
                            total_rating: li.getAttribute("data-total-rating") || "",
                            years: li.getAttribute("data-year") || "",
                            partner_id: li.getAttribute("data-partner-id") || ""
                        };
                    }
                """)
            except Exception:
                continue

            if not card_data.get("company_name"):
                continue

            partner_profile_url = build_zoho_profile_url(card_data.get("partner_id", ""))

            raw_partners.append({
                "card_data": card_data,
                "partner_profile_url": partner_profile_url
            })

        browser.close()

    profile_urls = [
        item["partner_profile_url"]
        for item in raw_partners
        if item.get("partner_profile_url")
    ]

    profile_results = get_zoho_profiles_fast(profile_urls, concurrency=4)

    for item in raw_partners:
        card_data = item["card_data"]
        partner_profile_url = item["partner_profile_url"]
        profile_details = profile_results.get(partner_profile_url, {})

        email = profile_details.get("contact_email") or card_data.get("email", "")
        website = profile_details.get("website") or website_from_email(email)
        linkedin = profile_details.get("linkedin", "")
        phone = profile_details.get("phone", "")

        partners.append({
            "platform": "Zoho",
            "ecosystem": "Zoho",
            "company_name": card_data.get("company_name", ""),
            "location": clean_location(card_data.get("location", "")),
            "services_offered": card_data.get("services_offered", ""),
            "contact_details": email,
            "contact_email": email,
            "phone": phone,
            "website": website,
            "partner_profile_url": partner_profile_url,
            "linkedin": linkedin,
            "source_url": ZOHO_DIRECTORY_URL,
            "confidence_score": card_data.get("rating", ""),
            "notes": (
                f"Tier: {card_data.get('tier', '')}; "
                f"Categories: {card_data.get('categories', '')}; "
                f"Industries: {card_data.get('industry', '')}; "
                f"Years: {card_data.get('years', '')}; "
                f"Ratings: {card_data.get('total_rating', '')}"
            )
        })

    return remove_duplicate_partners(partners)

def get_zoho_directories():
    return [
        {
            "platform": "Zoho",
            "directory_name": "Zoho Partner Directory",
            "url": ZOHO_DIRECTORY_URL,
            "source_url": ZOHO_DIRECTORY_URL
        }
    ]

def build_microsoft_additional_info_url(profile_url):
    if not profile_url:
        return ""

    if "/additionalInfo" in profile_url:
        return profile_url

    match = re.search(r"/partners/([^/?#]+)", profile_url)

    if not match:
        return profile_url

    partner_id = match.group(1)
    return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"


def extract_microsoft_partner_id(text):
    if not text:
        return ""

    match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        text
    )

    return match.group(0) if match else ""


def extract_microsoft_profile_url_from_links(base_url, links):
    for href in links:
        if not href:
            continue

        full_url = urljoin(base_url, href)

        if "/partners/" in full_url:
            return build_microsoft_additional_info_url(full_url)

    return ""
def microsoft_overview_to_additional_info(url):
    if not url:
        return ""

    url = url.split("?")[0].split("#")[0]

    if "/additionalInfo" in url:
        return url

    if "/overview" in url:
        return url.replace("/overview", "/additionalInfo")

    partner_id = extract_microsoft_partner_id(url)

    if partner_id:
        return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"

    return ""


def build_microsoft_profile_url_from_card_data(card_data):
    for href in card_data.get("links", []):
        profile_url = extract_microsoft_profile_url_from_links(MICROSOFT_PARTNER_URL, [href])

        if profile_url and profile_url != MICROSOFT_PARTNER_URL:
            return profile_url

    search_text = " ".join([
        card_data.get("html", ""),
        " ".join(card_data.get("links", [])),
        " ".join(card_data.get("attrs", []))
    ])

    partner_id = extract_microsoft_partner_id(search_text)

    if partner_id:
        return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"

    return ""

def build_microsoft_profile_url_from_card_html(card_html):
    partner_id = extract_microsoft_partner_id(card_html)

    if not partner_id:
        return ""

    return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"
def fetch_microsoft_partner_details(partner_id):
    try:
        url = (
            "https://main.prod.marketplacepartnerdirectory.azure.com/api/partners/"
            + partner_id
        )

        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        details = data.get("partnerDetails", {})

        contacts = details.get("contacts", [])

        print("\nCONTACTS:")
        print(contacts)

        email = ""
        phone = ""
        print("API Name :", details.get("name"))
        print("LinkedIn:", details.get("linkedInOrganizationProfile"))
        for contact in contacts:
            if not email:
                email = (
                    contact.get("email")
                    or contact.get("contactEmail")
                    or ""
                )

            if not phone:
                phone = (
                    contact.get("phone")
                    or contact.get("phoneNumber")
                    or ""
                )

        return {
            "website": details.get("url", ""),
            "linkedin": details.get(
                "linkedInOrganizationProfile",
                ""
            ),
            "contact_email": email,
            "phone": phone
        }

    except Exception as e:
        print("API ERROR:", partner_id, e)

        return {
            "website": "",
            "linkedin": "",
            "contact_email": "",
            "phone": ""
        }

def get_microsoft_directories():
    directories = []

    html = fetch_page(MICROSOFT_DIRECTORY_URL)
    soup = parse_page(html)

    for link in soup.find_all("a"):
        text = link.get_text(" ", strip=True)
        href = link.get("href")

        if not text or not href:
            continue

        full_url = urljoin(MICROSOFT_DIRECTORY_URL, href)

        if "microsoftpartners.microsoft.com/abs/" not in full_url:
            continue

        if full_url.rstrip("/") == MICROSOFT_DIRECTORY_URL.rstrip("/"):
            continue

        directories.append({
            "platform": "Microsoft",
            "directory_name": text,
            "url": full_url,
            "source_url": MICROSOFT_DIRECTORY_URL
        })

    return remove_duplicate_directories(directories)


def parse_microsoft_card_lines(lines):
    company_name = lines[0] if lines else ""
    location = lines[1] if len(lines) > 1 else ""

    services = []
    description_parts = []

    for line in lines[2:]:
        if line.lower() == "contact me":
            continue

        if line.startswith("+"):
            continue

        if len(description_parts) == 0 and len(line) <= 40:
            services.append(line)
        else:
            description_parts.append(line)

    return {
        "company_name": company_name,
        "location": location,
        "services_offered": ", ".join(services),
        "description": " ".join(description_parts)
    }


def scrape_microsoft_current_page(page, frame):
    partners = []

    frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)

    cards = frame.locator('div[role="listitem"]')
    count = cards.count()

    for index in range(count):
        card = cards.nth(index)

        try:
            text = card.inner_text(timeout=3000).strip()
        except Exception:
            continue

        lines = clean_lines(text)

        if not lines:
            continue

        parsed = parse_microsoft_card_lines(lines)
        profile_url = ""

        try:
            card_html = card.evaluate("element => element.outerHTML || ''")
            profile_url = build_microsoft_profile_url_from_card_html(card_html)
        except Exception:
            profile_url = ""


        except Exception:
            try:
                page.go_back(wait_until="domcontentloaded", timeout=30000)
                frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)
            except Exception:
                pass

        partners.append({
            "platform": "Microsoft",
            "ecosystem": "Microsoft",
            "company_name": parsed["company_name"],
            "location": parsed["location"],
            "services_offered": parsed["services_offered"],
            "website": "",
            "partner_profile_url": profile_url,
            "linkedin": "",
            "source_url": MICROSOFT_PARTNER_URL,
            "contact_email": "",
            "phone": "",
            "confidence_score": "",
            "notes": parsed["description"]
        })

    return partners

def click_microsoft_next_page(frame):
    next_buttons = [
        'button[aria-label="Next page"]',
        'button[title="Next page"]',
        'button:has-text("Next")',
        'a[aria-label="Next page"]',
        'a:has-text("Next")'
    ]

    for selector in next_buttons:
        try:
            button = frame.locator(selector).first

            if button.count() == 0:
                continue

            if button.is_disabled():
                continue

            button.click()

            frame.locator('div[role="listitem"]').nth(0).wait_for(timeout=8000)
            frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)
            return True

        except Exception:
            continue

    return False


def enrich_one_partner(partner):

    profile_url = partner.get("partner_profile_url", "")

    partner_id = extract_microsoft_partner_id(profile_url)

    if not partner_id:
        return partner

    details = fetch_microsoft_partner_details(partner_id)

    partner["website"] = details["website"]
    partner["linkedin"] = details["linkedin"]
    partner["contact_email"] = details["contact_email"]
    partner["contact_details"] = details["contact_email"]
    partner["phone"] = details["phone"]
    print("=" * 80)
    print("Company :", partner["company_name"])
    print("Profile :", profile_url)
    print("Partner :", partner_id)
    return partner


def enrich_microsoft_partners_fast(partners, concurrency=10):

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        partners = list(executor.map(enrich_one_partner, partners))

    return partners

def scrape_microsoft_partners(max_pages=5):
    all_partners = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(
            MICROSOFT_PARTNER_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        frame = page.frame_locator('iframe[title="Partners"]')

        try:
            frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)
        except Exception:
            print("No Microsoft partner cards found.")
            print(page.locator("body").inner_text()[:2000])
            browser.close()
            return []

        for page_number in range(max_pages):
            page_partners = scrape_microsoft_current_page(page,frame)
            all_partners.extend(page_partners)

            print(f"Scraped Microsoft page {page_number + 1}: {len(page_partners)} partners")

            moved = click_microsoft_next_page(frame)

            if not moved:
                break

            page.wait_for_timeout(500)

        browser.close()

    return remove_duplicate_partners(all_partners)

def get_domain_from_email(email):
    if not email or "@" not in email:
        return ""

    return email.split("@")[-1].strip().lower()


def website_from_email(email):
    domain = get_domain_from_email(email)

    if not domain:
        return ""

    blocked_domains = {
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com"
    }

    if domain in blocked_domains:
        return ""

    return f"https://{domain}"


def get_public_company_pages(website):
    pages = []

    if not website:
        return pages

    candidate_urls = [
        website,
        urljoin(website, "/about"),
        urljoin(website, "/about-us"),
        urljoin(website, "/contact"),
        urljoin(website, "/contact-us")
    ]

    for url in candidate_urls:
        try:
            html = fetch_page(url)
            soup = parse_page(html)
            text = soup.get_text(" ", strip=True)

            pages.append({
                "url": url,
                "html": html,
                "text": text
            })
        except Exception:
            continue

    return pages

def extract_public_details_from_website(website):
    details = {
        "website": website,
        "linkedin": "",
        "phone": ""
    }

    pages = get_public_company_pages(website)

    if pages:
        combined_text = " ".join(page["text"] for page in pages)

        details["phone"] = extract_phone(combined_text)
        details["linkedin"] = extract_linkedin_from_pages(pages)

    if not details["linkedin"]:
        details["linkedin"] = extract_linkedin_from_website_with_playwright(website)

    return details




def enrich_partner_public_details(partner):
    website = partner.get("website", "")

    if website and not is_company_website(website):
        website = ""

    if not website:
        website = website_from_email(partner.get("contact_email", ""))

    partner["website"] = website

    if website:
        public_details = extract_public_details_from_website(website)

        if public_details.get("linkedin"):
            partner["linkedin"] = public_details["linkedin"]

        if public_details.get("phone"):
            partner["phone"] = public_details["phone"]

    return partner

def get_partner_directories(platform):
    if platform == "Zoho":
        return get_zoho_directories()

    if platform == "Microsoft":
        return get_microsoft_directories()

    if platform == "Both":
        return get_zoho_directories() + get_microsoft_directories()

    return []


def get_partners(platform, enrich_details=True):
    if platform == "Zoho":
        partners = scrape_zoho_partners()

    elif platform == "Microsoft":
        partners = scrape_microsoft_partners(max_pages=6)

        if enrich_details:
            partners = enrich_microsoft_partners_fast(partners, concurrency=4)

    elif platform == "Both":
        zoho_partners = scrape_zoho_partners()
        microsoft_partners = scrape_microsoft_partners(max_pages=6)

        if enrich_details:
            microsoft_partners = enrich_microsoft_partners_fast(
                microsoft_partners,
                concurrency=4
            )

        partners = zoho_partners + microsoft_partners

    else:
        partners = []

    return partners



def clean_linkedin_url(url):
    if not url:
        return ""

    url = html.unescape(url)
    url = unquote(url)
    url = url.strip()
    url = url.split("?")[0].split("#")[0].rstrip("/")

    if url.startswith("www.linkedin.com"):
        url = "https://" + url

    return url


def is_linkedin_company_url(url):
    url = clean_linkedin_url(url)

    if not url:
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.lower().rstrip("/")

    if not domain.endswith("linkedin.com"):
        return False

    if path.startswith("/company/"):
        return True

    return False


def extract_linkedin_urls_from_text(text):
    if not text:
        return []

    text = html.unescape(unquote(text))

    matches = re.findall(
        r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[A-Za-z0-9_.%/-]+",
        text,
        flags=re.IGNORECASE
    )

    matches += re.findall(
        r"www\.linkedin\.com/company/[A-Za-z0-9_.%/-]+",
        text,
        flags=re.IGNORECASE
    )

    cleaned = []

    for match in matches:
        linkedin_url = clean_linkedin_url(match)

        if is_linkedin_company_url(linkedin_url):
            cleaned.append(linkedin_url)

    return cleaned


def extract_linkedin_from_links(base_url, hrefs):
    for href in hrefs:
        if not href:
            continue

        full_url = clean_linkedin_url(urljoin(base_url, href))

        if is_linkedin_company_url(full_url):
            return full_url

        embedded_urls = extract_linkedin_urls_from_text(href)

        if embedded_urls:
            return embedded_urls[0]

    return ""


def extract_linkedin_from_pages(pages):
    for page_data in pages:
        soup = parse_page(page_data["html"])

        hrefs = [
            link.get("href", "")
            for link in soup.find_all("a")
        ]

        linkedin = extract_linkedin_from_links(page_data["url"], hrefs)

        if linkedin:
            return linkedin

        linkedin_urls = extract_linkedin_urls_from_text(page_data["html"])

        if linkedin_urls:
            return linkedin_urls[0]

    return ""


def extract_linkedin_from_website_with_playwright(website):
    if not website:
        return ""

    candidate_urls = [
        website,
        urljoin(website, "/about"),
        urljoin(website, "/about-us"),
        urljoin(website, "/contact"),
        urljoin(website, "/contact-us")
    ]

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            for url in candidate_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)

                    hrefs = page.locator("a").evaluate_all(
                        "links => links.map(link => link.href || link.getAttribute('href') || '')"
                    )

                    linkedin = extract_linkedin_from_links(url, hrefs)

                    if linkedin:
                        browser.close()
                        return linkedin

                    rendered_html = page.content()
                    linkedin_urls = extract_linkedin_urls_from_text(rendered_html)

                    if linkedin_urls:
                        browser.close()
                        return linkedin_urls[0]

                except Exception:
                    continue

            browser.close()

    except Exception:
        pass

    return ""



=======
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from playwright.sync_api import sync_playwright
from ai_extractor import extract_missing_contact_fields_with_ai
from config import USER_AGENT, TIMEOUT
import html
import asyncio
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor


ZOHO_DIRECTORY_URL = "https://www.zoho.com/partners/find-zoho-partner.html"
MICROSOFT_DIRECTORY_URL = "https://microsoftpartners.microsoft.com/abs/Partner-Directories/"
MICROSOFT_PARTNER_URL = "https://marketplace.microsoft.com/en-us/marketplace/partner-dir"


def fetch_page(url):
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.text


def parse_page(html):
    return BeautifulSoup(html, "html.parser")


def clean_lines(text):
    return [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]


def clean_location(location):
    location = location.replace("\xa0", " ")
    location = re.sub(r"([a-z])India", r"\1, India", location)
    location = re.sub(r"([A-Z][a-z]+)India", r"\1, India", location)
    return " ".join(location.split()).strip()


def extract_email(text):
    emails = re.findall(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        text
    )
    return emails[0] if emails else ""


def extract_phone(text):
    phones = re.findall(r"\+?\d[\d\s().-]{7,}\d", text)
    return phones[0].strip() if phones else ""

def is_company_website(url):
    if not url or not url.startswith("http"):
        return False

    blocked_domains = [
        "zoho.com",
        "zohocorp.com",
        "microsoft.com",
        "microsoftpartners.microsoft.com",
        "marketplace.microsoft.com",
        "appsource.microsoft.com",
        "microsoftcloudpartner.eventbuilder.com",
        "eventbuilder.com",
        "aka.ms",
        "learn.microsoft.com",
        "support.microsoft.com",
        "go.microsoft.com",
        "cdn-dynmedia-1.microsoft.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "instagram.com",
        "linkedin.com",
        "youtube-nocookie.com"
    ]

    domain = urlparse(url).netloc.lower().replace("www.", "")

    return not any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in blocked_domains
    )


def extract_company_website_from_links(base_url, links):
    for href in links:
        if not href:
            continue

        full_url = urljoin(base_url, href).split("#")[0].strip()

        if is_company_website(full_url):
            return full_url.rstrip("/")

    return ""


def extract_company_website_from_html(html, base_url):
    soup = parse_page(html)
    hrefs = [link.get("href", "") for link in soup.find_all("a")]
    return extract_company_website_from_links(base_url, hrefs)


def remove_duplicate_partners(partners):
    unique = []
    seen = set()

    for partner in partners:
        key = (
            partner.get("ecosystem", "").lower(),
            partner.get("company_name", "").lower(),
            partner.get("website", "").lower(),
            partner.get("partner_profile_url", "").lower()
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(partner)

    return unique


def remove_duplicate_directories(directories):
    unique = []
    seen = set()

    for directory in directories:
        key = directory["url"].lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(directory)

    return unique


def build_zoho_profile_url(partner_id):
    if not partner_id:
        return ""

    return f"https://www.zoho.com/partners/find-partner-profile.html?partnerid={partner_id}"

def clean_url(url):
    if not url:
        return ""

    url = url.strip()

    if url == "#":
        return ""

    return url.split("?")[0].split("#")[0].rstrip("/")


def extract_email_from_href(href):
    if not href:
        return ""

    href = href.strip()

    if href.lower().startswith("mailto:"):
        email = href.split(":", 1)[1].split("?")[0].strip()
        return email if extract_email(email) else ""

    return extract_email(href)


def extract_phone_from_href(href):
    if not href:
        return ""

    href = href.strip()

    if href.lower().startswith("tel:"):
        return href.split(":", 1)[1].split("?")[0].strip()

    return ""


def is_partner_contact_email(email):
    if not email:
        return False

    domain = email.split("@")[-1].strip().lower()

    blocked_domains = {
        "microsoft.com",
        "zohocorp.com",
        "zoho.com"
    }

    return domain not in blocked_domains


def is_valid_linkedin_url(url):
    url = clean_url(url)

    if not url:
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    return domain.endswith("linkedin.com")


async def extract_zoho_profile_details_async(context, profile_url):
    details = {
        "website": "",
        "linkedin": "",
        "phone": "",
        "contact_email": ""
    }

    if not profile_url:
        return profile_url, details

    page = await context.new_page()

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_selector(".zwc-details-common", timeout=12000)
        except Exception:
            pass

        try:
            website = await page.locator("a.zwc-pr-weblink").first.get_attribute(
                "href",
                timeout=3000
            )
            website = clean_url(website)

            if is_company_website(website):
                details["website"] = website
        except Exception:
            pass

        try:
            linkedin = await page.locator("a.zwc-pr-linkedin").first.get_attribute(
                "href",
                timeout=3000
            )
            linkedin = clean_url(linkedin)

            if is_valid_linkedin_url(linkedin):
                details["linkedin"] = linkedin
        except Exception:
            pass

        if not details["linkedin"]:
            hrefs = await page.locator("a").evaluate_all(
                "links => links.map(link => link.href || link.getAttribute('href') || '')"
            )

            for href in hrefs:
                href = clean_url(href)

                if is_valid_linkedin_url(href):
                    details["linkedin"] = href
                    break

        body_text = await page.locator("body").inner_text(timeout=5000)
        details["phone"] = extract_phone(body_text)
        details["contact_email"] = extract_email(body_text)

    except Exception as error:
        details["profile_error"] = str(error)[:200]

    finally:
        await page.close()

    return profile_url, details





async def fetch_zoho_profiles_fast(profile_urls, concurrency=4):
    results = {}
    profile_urls = list(dict.fromkeys([url for url in profile_urls if url]))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()

        async def block_heavy_assets(route):
            resource_type = route.request.resource_type

            if resource_type in {"image", "media", "font"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", block_heavy_assets)

        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(profile_url):
            async with semaphore:
                return await extract_zoho_profile_details_async(context, profile_url)

        tasks = [run_one(url) for url in profile_urls]

        for task in asyncio.as_completed(tasks):
            profile_url, details = await task
            results[profile_url] = details

        await browser.close()

    return results


def get_zoho_profiles_fast(profile_urls, concurrency=4):
    def runner():
        return asyncio.run(
            fetch_zoho_profiles_fast(profile_urls, concurrency=concurrency)
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(runner).result()



async def fetch_zoho_profiles_fast(profile_urls, concurrency=8):
    results = {}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()

        async def block_heavy_assets(route):
            resource_type = route.request.resource_type

            if resource_type in {"image", "media", "font", "stylesheet"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", block_heavy_assets)

        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(profile_url):
            async with semaphore:
                return await extract_zoho_profile_details_async(context, profile_url)

        tasks = [
            run_one(profile_url)
            for profile_url in profile_urls
            if profile_url
        ]

        for task in asyncio.as_completed(tasks):
            profile_url, details = await task
            results[profile_url] = details

        await browser.close()

    return results


def get_zoho_profiles_fast(profile_urls, concurrency=8):
    return asyncio.run(fetch_zoho_profiles_fast(profile_urls, concurrency=concurrency))


def scrape_zoho_partners():
    partners = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(ZOHO_DIRECTORY_URL, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_selector(".res-partner-details", timeout=30000)
        except Exception:
            page.wait_for_timeout(8000)

        cards = page.locator(".res-partner-details").all()
        raw_partners = []

        for card in cards:
            try:
                card_data = card.evaluate("""
                    element => {
                        const li = element.closest("li") || element;

                        return {
                            company_name: element.querySelector(".res-name")?.innerText?.trim() || "",
                            location: element.querySelector(".zwc-cd-address")?.innerText?.trim() || "",
                            email: element.querySelector(".zwc-cd-mailid a")?.innerText?.trim() || "",
                            services_offered: li.getAttribute("data-practice") || "",
                            tier: li.getAttribute("data-tier") || "",
                            categories: li.getAttribute("data-categories") || "",
                            industry: li.getAttribute("data-industry") || "",
                            rating: li.getAttribute("data-avg-rating") || "",
                            total_rating: li.getAttribute("data-total-rating") || "",
                            years: li.getAttribute("data-year") || "",
                            partner_id: li.getAttribute("data-partner-id") || ""
                        };
                    }
                """)
            except Exception:
                continue

            if not card_data.get("company_name"):
                continue

            partner_profile_url = build_zoho_profile_url(card_data.get("partner_id", ""))

            raw_partners.append({
                "card_data": card_data,
                "partner_profile_url": partner_profile_url
            })

        browser.close()

    profile_urls = [
        item["partner_profile_url"]
        for item in raw_partners
        if item.get("partner_profile_url")
    ]

    profile_results = get_zoho_profiles_fast(profile_urls, concurrency=4)

    for item in raw_partners:
        card_data = item["card_data"]
        partner_profile_url = item["partner_profile_url"]
        profile_details = profile_results.get(partner_profile_url, {})

        email = profile_details.get("contact_email") or card_data.get("email", "")
        website = profile_details.get("website") or website_from_email(email)
        linkedin = profile_details.get("linkedin", "")
        phone = profile_details.get("phone", "")

        partners.append({
            "platform": "Zoho",
            "ecosystem": "Zoho",
            "company_name": card_data.get("company_name", ""),
            "location": clean_location(card_data.get("location", "")),
            "services_offered": card_data.get("services_offered", ""),
            "contact_details": email,
            "contact_email": email,
            "phone": phone,
            "website": website,
            "partner_profile_url": partner_profile_url,
            "linkedin": linkedin,
            "source_url": ZOHO_DIRECTORY_URL,
            "confidence_score": card_data.get("rating", ""),
            "notes": (
                f"Tier: {card_data.get('tier', '')}; "
                f"Categories: {card_data.get('categories', '')}; "
                f"Industries: {card_data.get('industry', '')}; "
                f"Years: {card_data.get('years', '')}; "
                f"Ratings: {card_data.get('total_rating', '')}"
            )
        })

    return remove_duplicate_partners(partners)

def get_zoho_directories():
    return [
        {
            "platform": "Zoho",
            "directory_name": "Zoho Partner Directory",
            "url": ZOHO_DIRECTORY_URL,
            "source_url": ZOHO_DIRECTORY_URL
        }
    ]

def build_microsoft_additional_info_url(profile_url):
    if not profile_url:
        return ""

    if "/additionalInfo" in profile_url:
        return profile_url

    match = re.search(r"/partners/([^/?#]+)", profile_url)

    if not match:
        return profile_url

    partner_id = match.group(1)
    return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"


def extract_microsoft_partner_id(text):
    if not text:
        return ""

    match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        text
    )

    return match.group(0) if match else ""


def extract_microsoft_profile_url_from_links(base_url, links):
    for href in links:
        if not href:
            continue

        full_url = urljoin(base_url, href)

        if "/partners/" in full_url:
            return build_microsoft_additional_info_url(full_url)

    return ""
def microsoft_overview_to_additional_info(url):
    if not url:
        return ""

    url = url.split("?")[0].split("#")[0]

    if "/additionalInfo" in url:
        return url

    if "/overview" in url:
        return url.replace("/overview", "/additionalInfo")

    partner_id = extract_microsoft_partner_id(url)

    if partner_id:
        return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"

    return ""


def build_microsoft_profile_url_from_card_data(card_data):
    for href in card_data.get("links", []):
        profile_url = extract_microsoft_profile_url_from_links(MICROSOFT_PARTNER_URL, [href])

        if profile_url and profile_url != MICROSOFT_PARTNER_URL:
            return profile_url

    search_text = " ".join([
        card_data.get("html", ""),
        " ".join(card_data.get("links", [])),
        " ".join(card_data.get("attrs", []))
    ])

    partner_id = extract_microsoft_partner_id(search_text)

    if partner_id:
        return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"

    return ""

def build_microsoft_profile_url_from_card_html(card_html):
    partner_id = extract_microsoft_partner_id(card_html)

    if not partner_id:
        return ""

    return f"https://marketplace.microsoft.com/en-us/partners/{partner_id}/additionalInfo"
def fetch_microsoft_partner_details(partner_id):
    try:
        url = (
            "https://main.prod.marketplacepartnerdirectory.azure.com/api/partners/"
            + partner_id
        )

        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        details = data.get("partnerDetails", {})

        contacts = details.get("contacts", [])

        print("\nCONTACTS:")
        print(contacts)

        email = ""
        phone = ""
        print("API Name :", details.get("name"))
        print("LinkedIn:", details.get("linkedInOrganizationProfile"))
        for contact in contacts:
            if not email:
                email = (
                    contact.get("email")
                    or contact.get("contactEmail")
                    or ""
                )

            if not phone:
                phone = (
                    contact.get("phone")
                    or contact.get("phoneNumber")
                    or ""
                )

        return {
            "website": details.get("url", ""),
            "linkedin": details.get(
                "linkedInOrganizationProfile",
                ""
            ),
            "contact_email": email,
            "phone": phone
        }

    except Exception as e:
        print("API ERROR:", partner_id, e)

        return {
            "website": "",
            "linkedin": "",
            "contact_email": "",
            "phone": ""
        }

def get_microsoft_directories():
    directories = []

    html = fetch_page(MICROSOFT_DIRECTORY_URL)
    soup = parse_page(html)

    for link in soup.find_all("a"):
        text = link.get_text(" ", strip=True)
        href = link.get("href")

        if not text or not href:
            continue

        full_url = urljoin(MICROSOFT_DIRECTORY_URL, href)

        if "microsoftpartners.microsoft.com/abs/" not in full_url:
            continue

        if full_url.rstrip("/") == MICROSOFT_DIRECTORY_URL.rstrip("/"):
            continue

        directories.append({
            "platform": "Microsoft",
            "directory_name": text,
            "url": full_url,
            "source_url": MICROSOFT_DIRECTORY_URL
        })

    return remove_duplicate_directories(directories)


def parse_microsoft_card_lines(lines):
    company_name = lines[0] if lines else ""
    location = lines[1] if len(lines) > 1 else ""

    services = []
    description_parts = []

    for line in lines[2:]:
        if line.lower() == "contact me":
            continue

        if line.startswith("+"):
            continue

        if len(description_parts) == 0 and len(line) <= 40:
            services.append(line)
        else:
            description_parts.append(line)

    return {
        "company_name": company_name,
        "location": location,
        "services_offered": ", ".join(services),
        "description": " ".join(description_parts)
    }


def scrape_microsoft_current_page(page, frame):
    partners = []

    frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)

    cards = frame.locator('div[role="listitem"]')
    count = cards.count()

    for index in range(count):
        card = cards.nth(index)

        try:
            text = card.inner_text(timeout=3000).strip()
        except Exception:
            continue

        lines = clean_lines(text)

        if not lines:
            continue

        parsed = parse_microsoft_card_lines(lines)
        profile_url = ""

        try:
            card_html = card.evaluate("element => element.outerHTML || ''")
            profile_url = build_microsoft_profile_url_from_card_html(card_html)
        except Exception:
            profile_url = ""


        except Exception:
            try:
                page.go_back(wait_until="domcontentloaded", timeout=30000)
                frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)
            except Exception:
                pass

        partners.append({
            "platform": "Microsoft",
            "ecosystem": "Microsoft",
            "company_name": parsed["company_name"],
            "location": parsed["location"],
            "services_offered": parsed["services_offered"],
            "website": "",
            "partner_profile_url": profile_url,
            "linkedin": "",
            "source_url": MICROSOFT_PARTNER_URL,
            "contact_email": "",
            "phone": "",
            "confidence_score": "",
            "notes": parsed["description"]
        })

    return partners

def click_microsoft_next_page(frame):
    next_buttons = [
        'button[aria-label="Next page"]',
        'button[title="Next page"]',
        'button:has-text("Next")',
        'a[aria-label="Next page"]',
        'a:has-text("Next")'
    ]

    for selector in next_buttons:
        try:
            button = frame.locator(selector).first

            if button.count() == 0:
                continue

            if button.is_disabled():
                continue

            button.click()

            frame.locator('div[role="listitem"]').nth(0).wait_for(timeout=8000)
            frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)
            return True

        except Exception:
            continue

    return False


def enrich_one_partner(partner):

    profile_url = partner.get("partner_profile_url", "")

    partner_id = extract_microsoft_partner_id(profile_url)

    if not partner_id:
        return partner

    details = fetch_microsoft_partner_details(partner_id)

    partner["website"] = details["website"]
    partner["linkedin"] = details["linkedin"]
    partner["contact_email"] = details["contact_email"]
    partner["contact_details"] = details["contact_email"]
    partner["phone"] = details["phone"]
    print("=" * 80)
    print("Company :", partner["company_name"])
    print("Profile :", profile_url)
    print("Partner :", partner_id)
    return partner


def enrich_microsoft_partners_fast(partners, concurrency=10):

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        partners = list(executor.map(enrich_one_partner, partners))

    return partners

def scrape_microsoft_partners(max_pages=5):
    all_partners = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(
            MICROSOFT_PARTNER_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        frame = page.frame_locator('iframe[title="Partners"]')

        try:
            frame.locator('div[role="listitem"]').first.wait_for(timeout=30000)
        except Exception:
            print("No Microsoft partner cards found.")
            print(page.locator("body").inner_text()[:2000])
            browser.close()
            return []

        for page_number in range(max_pages):
            page_partners = scrape_microsoft_current_page(page,frame)
            all_partners.extend(page_partners)

            print(f"Scraped Microsoft page {page_number + 1}: {len(page_partners)} partners")

            moved = click_microsoft_next_page(frame)

            if not moved:
                break

            page.wait_for_timeout(500)

        browser.close()

    return remove_duplicate_partners(all_partners)

def get_domain_from_email(email):
    if not email or "@" not in email:
        return ""

    return email.split("@")[-1].strip().lower()


def website_from_email(email):
    domain = get_domain_from_email(email)

    if not domain:
        return ""

    blocked_domains = {
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com"
    }

    if domain in blocked_domains:
        return ""

    return f"https://{domain}"


def get_public_company_pages(website):
    pages = []

    if not website:
        return pages

    candidate_urls = [
        website,
        urljoin(website, "/about"),
        urljoin(website, "/about-us"),
        urljoin(website, "/contact"),
        urljoin(website, "/contact-us")
    ]

    for url in candidate_urls:
        try:
            html = fetch_page(url)
            soup = parse_page(html)
            text = soup.get_text(" ", strip=True)

            pages.append({
                "url": url,
                "html": html,
                "text": text
            })
        except Exception:
            continue

    return pages

def extract_public_details_from_website(website):
    details = {
        "website": website,
        "linkedin": "",
        "phone": ""
    }

    pages = get_public_company_pages(website)

    if pages:
        combined_text = " ".join(page["text"] for page in pages)

        details["phone"] = extract_phone(combined_text)
        details["linkedin"] = extract_linkedin_from_pages(pages)

    if not details["linkedin"]:
        details["linkedin"] = extract_linkedin_from_website_with_playwright(website)

    return details




def enrich_partner_public_details(partner):
    website = partner.get("website", "")

    if website and not is_company_website(website):
        website = ""

    if not website:
        website = website_from_email(partner.get("contact_email", ""))

    partner["website"] = website

    if website:
        public_details = extract_public_details_from_website(website)

        if public_details.get("linkedin"):
            partner["linkedin"] = public_details["linkedin"]

        if public_details.get("phone"):
            partner["phone"] = public_details["phone"]

    return partner

def get_partner_directories(platform):
    if platform == "Zoho":
        return get_zoho_directories()

    if platform == "Microsoft":
        return get_microsoft_directories()

    if platform == "Both":
        return get_zoho_directories() + get_microsoft_directories()

    return []


def get_partners(platform, enrich_details=True):
    if platform == "Zoho":
        partners = scrape_zoho_partners()

    elif platform == "Microsoft":
        partners = scrape_microsoft_partners(max_pages=6)

        if enrich_details:
            partners = enrich_microsoft_partners_fast(partners, concurrency=4)

    elif platform == "Both":
        zoho_partners = scrape_zoho_partners()
        microsoft_partners = scrape_microsoft_partners(max_pages=6)

        if enrich_details:
            microsoft_partners = enrich_microsoft_partners_fast(
                microsoft_partners,
                concurrency=4
            )

        partners = zoho_partners + microsoft_partners

    else:
        partners = []

    return partners



def clean_linkedin_url(url):
    if not url:
        return ""

    url = html.unescape(url)
    url = unquote(url)
    url = url.strip()
    url = url.split("?")[0].split("#")[0].rstrip("/")

    if url.startswith("www.linkedin.com"):
        url = "https://" + url

    return url


def is_linkedin_company_url(url):
    url = clean_linkedin_url(url)

    if not url:
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.lower().rstrip("/")

    if not domain.endswith("linkedin.com"):
        return False

    if path.startswith("/company/"):
        return True

    return False


def extract_linkedin_urls_from_text(text):
    if not text:
        return []

    text = html.unescape(unquote(text))

    matches = re.findall(
        r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[A-Za-z0-9_.%/-]+",
        text,
        flags=re.IGNORECASE
    )

    matches += re.findall(
        r"www\.linkedin\.com/company/[A-Za-z0-9_.%/-]+",
        text,
        flags=re.IGNORECASE
    )

    cleaned = []

    for match in matches:
        linkedin_url = clean_linkedin_url(match)

        if is_linkedin_company_url(linkedin_url):
            cleaned.append(linkedin_url)

    return cleaned


def extract_linkedin_from_links(base_url, hrefs):
    for href in hrefs:
        if not href:
            continue

        full_url = clean_linkedin_url(urljoin(base_url, href))

        if is_linkedin_company_url(full_url):
            return full_url

        embedded_urls = extract_linkedin_urls_from_text(href)

        if embedded_urls:
            return embedded_urls[0]

    return ""


def extract_linkedin_from_pages(pages):
    for page_data in pages:
        soup = parse_page(page_data["html"])

        hrefs = [
            link.get("href", "")
            for link in soup.find_all("a")
        ]

        linkedin = extract_linkedin_from_links(page_data["url"], hrefs)

        if linkedin:
            return linkedin

        linkedin_urls = extract_linkedin_urls_from_text(page_data["html"])

        if linkedin_urls:
            return linkedin_urls[0]

    return ""


def extract_linkedin_from_website_with_playwright(website):
    if not website:
        return ""

    candidate_urls = [
        website,
        urljoin(website, "/about"),
        urljoin(website, "/about-us"),
        urljoin(website, "/contact"),
        urljoin(website, "/contact-us")
    ]

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            for url in candidate_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)

                    hrefs = page.locator("a").evaluate_all(
                        "links => links.map(link => link.href || link.getAttribute('href') || '')"
                    )

                    linkedin = extract_linkedin_from_links(url, hrefs)

                    if linkedin:
                        browser.close()
                        return linkedin

                    rendered_html = page.content()
                    linkedin_urls = extract_linkedin_urls_from_text(rendered_html)

                    if linkedin_urls:
                        browser.close()
                        return linkedin_urls[0]

                except Exception:
                    continue

            browser.close()

    except Exception:
        pass

    return ""



>>>>>>> 7b15be9b74c68e546b1262fa3e7150fc3fc49ffc
