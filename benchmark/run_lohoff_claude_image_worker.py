#!/usr/bin/env python3
"""Install the image adapter only inside a benchmark recovery worker."""
from pathlib import Path
import runpy

import langchain_anthropic
from anthropic_images import ImageSafeChatAnthropic


def main():
    original = langchain_anthropic.ChatAnthropic
    langchain_anthropic.ChatAnthropic = ImageSafeChatAnthropic
    try:
        runpy.run_path(str(Path(__file__).with_name('run_lohoff_architecture_pilot.py')),
                      run_name='__main__')
    finally:
        langchain_anthropic.ChatAnthropic = original


if __name__ == '__main__':
    main()
