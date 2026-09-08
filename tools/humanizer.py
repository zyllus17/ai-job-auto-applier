import asyncio
import math
import random
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class HumanConfig:
    """Configuration for human-like timing parameters."""
    keystroke_mean_ms: float = 100.0
    keystroke_stddev_ms: float = 30.0
    cognitive_pause_min_ms: float = 250.0
    cognitive_pause_max_ms: float = 850.0
    typo_rate: float = 0.015
    pre_click_pause_min_ms: float = 50.0
    pre_click_pause_max_ms: float = 200.0
    post_click_pause_min_ms: float = 100.0
    post_click_pause_max_ms: float = 300.0
    field_switch_min_ms: float = 500.0
    field_switch_max_ms: float = 1800.0
    reading_min_ms: float = 2000.0
    reading_max_ms: float = 5000.0


def _generate_bezier_curve(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], num_points: int) -> List[Tuple[float, float]]:
    """Generate points along a cubic Bezier curve."""
    points = []
    for i in range(num_points):
        t = i / max(1, num_points - 1)
        # B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
        x = (1-t)**3 * p0[0] + 3 * (1-t)**2 * t * p1[0] + 3 * (1-t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3 * (1-t)**2 * t * p1[1] + 3 * (1-t) * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points

class HumanBehavior:
    """Simulates realistic human-like browser interactions."""
    
    def __init__(self, page=None, config: Optional[HumanConfig] = None):
        """Initialize with an optional Playwright page object and config."""
        self.page = page
        self.config = config or HumanConfig()
        
    def set_page(self, page):
        """Set or update the active page."""
        self.page = page

    async def type_text(self, element, text: str):
        """Alias for human_type to maintain API compatibility."""
        await self.human_type(element, text)
        
    async def _get_random_point_in_element(self, element) -> Optional[Tuple[float, float]]:
        """Get a random point within 20-80% of element's bounding box."""
        box = await element.bounding_box()
        if not box:
            return None
            
        x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
        y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
        return (x, y)
        
    async def move_to_element(self, element):
        """Move mouse to element using Bezier curve with Fitts's Law velocity."""
        try:
            target_point = await self._get_random_point_in_element(element)
            if not target_point:
                logger.warning("Could not get bounding box for element, skipping mouse move.")
                return
                
            # Current mouse position (we can't always get it easily in playwright without tracking, 
            # so we'll start from a random nearby point or (0,0))
            # In a real tracking scenario, we'd store the last mouse position.
            start_x = target_point[0] - random.uniform(100, 300)
            start_y = target_point[1] - random.uniform(100, 300)
            
            # Control points for Bezier curve
            cp1_x = start_x + (target_point[0] - start_x) * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
            cp1_y = start_y + (target_point[1] - start_y) * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
            
            cp2_x = start_x + (target_point[0] - start_x) * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
            cp2_y = start_y + (target_point[1] - start_y) * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
            
            # Generate curve with variable points based on distance (Fitts's law approximation)
            distance = math.hypot(target_point[0] - start_x, target_point[1] - start_y)
            num_steps = max(5, int(distance / 20))
            
            points = _generate_bezier_curve((start_x, start_y), (cp1_x, cp1_y), (cp2_x, cp2_y), target_point, num_steps)
            
            for x, y in points:
                # Add slight micro-tremor (Perlin noise simplified to random jitter)
                jitter_x = random.uniform(-1, 1)
                jitter_y = random.uniform(-1, 1)
                await self.page.mouse.move(x + jitter_x, y + jitter_y)
                # Fitts's law velocity approximation (slower near end)
                await asyncio.sleep(random.uniform(0.005, 0.02))
                
        except Exception as e:
            logger.error(f"Error in move_to_element: {e}")

    async def human_click(self, element):
        """Click with realistic behavior."""
        logger.info("Performing human click.")
        await self.move_to_element(element)
        
        # Pre-click pause
        await asyncio.sleep(random.uniform(
            self.config.pre_click_pause_min_ms, 
            self.config.pre_click_pause_max_ms) / 1000.0)
            
        target_point = await self._get_random_point_in_element(element)
        if target_point:
            await self.page.mouse.down()
            await asyncio.sleep(random.uniform(0.05, 0.15)) # Click duration
            await self.page.mouse.up()
        else:
            await element.click()
            
        # Post-click pause
        await asyncio.sleep(random.uniform(
            self.config.post_click_pause_min_ms, 
            self.config.post_click_pause_max_ms) / 1000.0)

    async def human_type(self, element, text: str):
        """Type text character by character with realistic timing."""
        logger.info(f"Performing human typing: {len(text)} chars")
        await self.human_click(element)
        
        # Clear existing content naturally
        await element.click(click_count=3)
        await self.page.keyboard.press("Backspace")
        await asyncio.sleep(0.2)
        
        for char in text:
            # Cognitive pause for spaces/punctuation
            if char in [" ", ".", ",", "!", "?"]:
                await asyncio.sleep(random.uniform(
                    self.config.cognitive_pause_min_ms, 
                    self.config.cognitive_pause_max_ms) / 1000.0)
            
            # Simulated typo
            if random.random() < self.config.typo_rate:
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                await self.page.keyboard.type(wrong_char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
            # Type actual character
            await self.page.keyboard.type(char)
            
            # Log-normal keystroke delay
            delay_ms = random.lognormvariate(
                math.log(self.config.keystroke_mean_ms), 
                math.log(1 + self.config.keystroke_stddev_ms/self.config.keystroke_mean_ms)
            )
            await asyncio.sleep(min(delay_ms / 1000.0, 0.5)) # Cap at 500ms
            
        # Dispatch blur to trigger change events
        await element.evaluate("e => e.blur()")
        await asyncio.sleep(0.2)

    async def human_scroll(self, direction='down', amount=300):
        """Scroll with human-like behavior."""
        logger.info(f"Performing human scroll {direction}.")
        scrolled = 0
        while scrolled < amount:
            step = random.uniform(80, 250)
            if direction == 'down':
                await self.page.mouse.wheel(0, step)
            else:
                await self.page.mouse.wheel(0, -step)
                
            scrolled += step
            # Inertial deceleration / reading pauses
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.8, 2.5))
            else:
                await asyncio.sleep(random.uniform(0.05, 0.15))

    async def wait_between_fields(self):
        """Random delay between switching form fields."""
        delay = random.uniform(
            self.config.field_switch_min_ms, 
            self.config.field_switch_max_ms) / 1000.0
        await asyncio.sleep(delay)

    async def wait_reading(self):
        """Simulate reading time when viewing a page."""
        delay = random.uniform(
            self.config.reading_min_ms, 
            self.config.reading_max_ms) / 1000.0
        await asyncio.sleep(delay)

    async def select_dropdown(self, element, value: str):
        """Select dropdown with human-like behavior."""
        logger.info(f"Selecting dropdown option: {value}")
        await self.human_click(element)
        await asyncio.sleep(random.uniform(0.3, 0.8)) # wait for options
        
        # Simulating scroll or finding the option
        await self.page.keyboard.type(value[:2]) # Type first few chars to focus
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await self.page.keyboard.press("Enter")
        await asyncio.sleep(random.uniform(0.2, 0.5))

    async def upload_file(self, file_input, file_path: str):
        """Upload file via file input with delay simulation."""
        logger.info(f"Uploading file: {file_path}")
        await self.move_to_element(file_input)
        
        # Simulating OS file dialog delay
        await asyncio.sleep(random.uniform(1.5, 3.5))
        await file_input.set_input_files(file_path)
        await asyncio.sleep(random.uniform(0.5, 1.5))
