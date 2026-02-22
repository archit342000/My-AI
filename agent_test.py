import asyncio
from browser_use import Agent, Browser, BrowserProfile, ChatOpenAI

# Configure the browser to use your system-installed Google Chrome
config = BrowserProfile(
    executable_path='/snap/bin/chromium', 
    headless=False
)

# Initialize the browser with your custom config
browser = Browser(browser_profile=config)

local_llm = ChatOpenAI(
    base_url="http://localhost:1234/v1", 
    api_key="lm-studio",
    model="qwen/qwen3-vl-30b",
    timeout=300,
    max_retries=0
)

async def main():
    agent = Agent(
        task="Find out who is the greatest footballer of all time.",
        llm=local_llm,
        browser=browser, 
        llm_timeout=300,
        max_failures=5
    )
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())