# Nairaland Thread Summarizer

A simple Python application that helps users keep up with Nairaland forum discussions by providing concise summaries of the latest thread pages, highlighting key discussions, and identifying representative posts using AI(Google Gemini Flash). There are informative threads that are highly valuable for marketing and research teams. This project was created to help keep up with relevant discussions without having to read through hundreds of posts.

## Overview

Nairaland Thread Summarizer is designed to solve the challenge of keeping up with long-running forum threads that span multiple pages and time periods. It helps users quickly understand the latest discussions without having to read through hundreds of posts.

## Features

- **Thread Summarization**: Get concise summaries of Nairaland thread pages
- **Trend Analysis**: Identify key discussion points and general opinions
- **Representative Posts**: Discover important posts that capture the essence of discussions
- **Time-Saving**: Quickly catch up on threads without reading every post
- **Flexible Usage**: Works for both new threads and long-running discussions

## How It Works

1. **Input**: Provide a Nairaland thread URL
2. **Scraping**: The application fetches the user specified number of latest pages of the thread to fetch. E.g if user specified 5 pages to scrape, the application will fetch the last 5 pages of the thread. Default is 2.
3. **Analysis**: Content is processed to identify key discussions and sentiments using Google Gemini.
4. **Summarization**: Generate a concise summary of the main points.
5. **Output**: Receive a summary with representative post links for further reading.


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This application is not affiliated with or endorsed by Nairaland. It is designed for personal, non-commercial use. Please respect Nairaland's terms of service and robots.txt when using this tool.
