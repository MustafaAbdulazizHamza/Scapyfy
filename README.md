# 🧙‍♂️ Scapyfy
**Scapyfy** is a secure **LLM agent** that performs packet crafting tasks on your behalf. The agent utilizes **OpenAI services** for intelligent decision-making and operates behind an **API** secured with **JWT** authentication.

The name is a portmanteau of the popular packet crafting tool, **Scapy**, and the suffix **-fy**, which evokes a sense of **Harry Potter** magic.

---

## 🛠️ Requirements

To run Scapyfy, you will need the following:

1.  A **Linux machine** (desktop, server, etc.).
2.  **Superuser privileges** (`sudo`).
3.  **Python 3**.

---

## 🚀 Installation

Follow these steps to get Scapyfy set up:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/MustafaAbdulazizHamza/Scapyfy.git](https://github.com/MustafaAbdulazizHamza/Scapyfy.git)
    cd Scapyfy
    ```
2.  **Install dependencies in a virtual environment:**
    * Create a virtual environment named `scapyfy-env` and activate it.
    * Install the required Python packages.
    ```bash
    python3 -m venv scapyfy-env
    source scapyfy-env/bin/activate
    python3 -m pip install -r requirements.txt
    ```
3.  **Set the API Key:**
    * Set the environment variable `OPENAI_API_KEY` to your OpenAI access key.
    * **Recommendation:** Use a `.env` file to securely store this secret:
    ```bash
    # .env file content
    OPENAI_API_KEY=<YOUR API KEY>
    ```

---

## 🏃 Execution

To run Scapyfy, simply execute the `execute.sh` script. Since packet crafting requires low-level access, the script must be run with **superuser privileges**.

You can optionally enable **HTTPS/TLS** by passing the paths to your digital certificates as command-line interface (CLI) parameters.

* **Execution without TLS:**
    ```bash
    sudo bash execute.sh
    ```
* **Execution with TLS:**
    ```bash
    sudo bash execute.sh <ssl_certfile_path> <ssl_keyfile_path>
    ```
## 📝 Notes

1.  **API Documentation:** The full API documentation is available at the `/docs` endpoint after execution.
2.  **CLI Tool:** To interact with Scapyfy from your terminal, you can use the dedicated command-line tool, **Scapyfy-CLI**, available [here](https://github.com/MustafaAbdulazizHamza/Scapyfy-CLI).
