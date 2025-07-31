Hey everyone, Jaanav Shah here, a Computer Engineering student at Purdue, and I’m excited to share a major stride in my latest project! As engineers, we're constantly looking for ways to streamline workflows, reduce friction, and make our digital lives more efficient. This project is all about tackling one of the most common productivity killers: context switching when you need a quick answer.

### The Quest for Seamless Knowledge: Building a Real-Time AI Teleprompter

Ever been deep in focus — coding, writing, or even just researching — when a question pops into your head? You know the drill: open a new tab, type your query, sift through results, and *then* try to get back into your flow. It’s disruptive, time-consuming, and often breaks your concentration.

My vision for this project was simple yet ambitious: **what if you could instantly query an AI and get an answer, right on your screen, without ever leaving your primary application?** Imagine a discrete, always-on-top overlay that acts as your personal, silent AI co-pilot, ready to assist with a simple hotkey.

This isn't just about getting answers faster; it's about maintaining a state of "flow" – that highly productive, deeply focused mental state where ideas connect effortlessly. By bringing AI-powered knowledge directly to your workspace, we can minimize distractions and maximize efficiency.

And with the latest updates, this vision is becoming a tangible reality. Let's dive into how we're making it happen!

### Under the Hood: The Architecture of Instant Insight

This iteration, marked as `v 1.0`, lays the foundational elements for our real-time AI teleprompter. We've built a robust, multi-component system designed for responsiveness and ease of use.

#### The Brain: Automating Google NotebookLM

At the core of our intelligent assistant is `notebook_automator.py`. This script is the "brain," responsible for interacting with Google's powerful NotebookLM. But how do we get it to "type" questions and "read" answers?

We leverage **Playwright**, a fantastic library for browser automation. Instead of building an LLM from scratch, `notebook_automator.py` connects to an *already running Chrome instance* (specifically, one debuggable on port 9222). This allows us to programmatically:

*   **Locate the NotebookLM Tab:** It intelligently finds the correct browser tab by its URL.
*   **Send Questions:** We use Playwright to simulate a user typing a question into NotebookLM's chat input field and pressing Enter.
*   **Scrape and Clean Responses:** Once NotebookLM processes the query, the script waits for the AI's response to appear. The real magic here is the sophisticated **response cleaning**. NotebookLM's output often includes UI elements, citations, and inconsistent formatting. Our script meticulously strips these away, normalizes whitespace, and properly formats bullet points, ensuring the displayed answer is clean, concise, and easy to read.

This approach means we're tapping into a powerful, pre-trained AI without the overhead of API keys or complex model deployments, making the setup much simpler for personal use.

#### The Communication Hub: Our Flask API

To decouple the AI automation from the user interface and allow for flexible interaction, we introduced `server.py` – a lightweight **Flask web server**.

This server exposes a single, crucial API endpoint: `/query`. When our UI needs an answer, it sends a POST request with a question to this endpoint. The `server.py` then:

*   **Receives Queries:** It takes the incoming question from the JSON body of the request.
*   **Delegates to NotebookLM:** It asynchronously calls our `query_notebook` function (from `notebook_automator.py`) with the user's question. Asynchronous processing is key here, ensuring the server remains responsive even while waiting for NotebookLM's potentially slow response.
*   **Returns Cleaned Responses:** Once `notebook_automator.py` provides the cleaned answer, `server.py` returns it as a JSON response to the UI.

This modular design makes our system incredibly flexible. In the future, we could easily swap out NotebookLM for a different LLM or integrate multiple AI services, all while keeping the UI consistent.

#### The User's Window: Crafting the Teleprompter UI

Finally, the most visible and interactive part of this update is `teleprompter_ui.py`. This is where the magic happens for the user, built using **Tkinter** for a native desktop feel.

The `teleprompter_ui.py` creates a unique, always-on-top window that feels less like an application and more like an integrated part of your desktop environment. Here's how it enhances the user experience:

*   **Seamless Overlay:** The window is **frameless** and **always on top**, meaning it floats above all other applications. It can be moved and resized by simply dragging a designated handle, allowing users to position it wherever it’s most convenient without obscuring critical content.
*   **Intuitive Interaction:** Users can type their questions into a dedicated entry field. Responses from our Flask API are dynamically displayed below, clearing previous content for new inquiries.
*   **Global Hotkey Control:** This is where the "teleprompter" truly comes alive. Using `pynput`, we've implemented a comprehensive global hotkey system for ultimate control without touching your mouse:
    *   `Ctrl+Enter`: Submit your query to the AI.
    *   `Ctrl+B`: Toggle the teleprompter window's visibility – make it appear when you need it, disappear when you don't.
    *   `Ctrl+Q`: Quit the application gracefully.
    *   `Ctrl+R`: Start a new problem session, clearing the input and response.
    *   `Ctrl+Arrow Keys`: Nudge the window precisely in any direction.
    *   `Ctrl+=` / `Ctrl+-`: Adjust the text zoom for readability.
    *   `Ctrl+0`: Reset text zoom to default.
    *   `Ctrl+]` / `Ctrl+[`: Increase or decrease window opacity, allowing you to fine-tune its presence.
*   **Responsive and Threaded:** API requests and hotkey listening run in separate threads, ensuring the UI remains perfectly responsive, even during network delays or while waiting for AI responses.
*   **Thoughtful Touches:** We've incorporated a sleek dark theme (`#282c34`) for a professional look and included platform-specific logic to ensure the window behaves well on Windows (e.g., as a tool window, not cluttering the taskbar). There's even a cleanup function to gracefully handle and close the Chrome instance on exit.

### The Impact: Your Personal AI Co-Pilot

With these pieces in place, we're building more than just an application; we're crafting a new way to interact with knowledge. This AI teleprompter empowers you to:

*   **Stay in Flow:** Get answers instantly without breaking your concentration.
*   **Enhance Productivity:** Reduce time spent searching and context-switching.
*   **Access Information Seamlessly:** Have an intelligent assistant always at your fingertips, ready to provide concise, cleaned information.

This `v 1.0` release is a significant leap towards a truly integrated, AI-powered desktop experience. It demonstrates the power of combining browser automation, web services, and native UI elements to create something genuinely useful and innovative.

### What's Next?

This is just the beginning! Future iterations will focus on:

*   Exploring alternative LLM backends and integrating more AI services.
*   Adding more sophisticated text manipulation and formatting options.
*   Further refining the UI and user experience based on feedback.

I'm incredibly excited about the potential of this project to transform how we interact with information and I'm eager to continue sharing my progress with you all.

Stay tuned for more updates, and happy engineering!

— Jaanav Shah