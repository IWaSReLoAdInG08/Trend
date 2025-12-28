import os
import sys
import argparse
import subprocess

def run_command(cmd_args):
    """Run a command with current python interpreter"""
    cmd = [sys.executable] + cmd_args
    return subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser(description="TrendRadar CLI")
    parser.add_argument("command", choices=["run", "fetch", "notify", "report", "server", "status", "mcp"], help="Command to run")
    parser.add_argument("--date", help="Date for report (YYYY-MM-DD)")
    parser.add_argument("--mode", choices=["stdio", "http"], default="stdio", help="MCP transport mode")
    parser.add_argument("--no-notify", action="store_true", help="Fetch data without sending notifications")
    
    args = parser.parse_args()

    if args.command == "fetch":
        print("Fetching news data...")
        cmd = ["fetch_news.py"]
        if args.no_notify:
            cmd.append("--no-notify")
        run_command(cmd)
    
    elif args.command == "notify":
        print("Sending notifications from existing data...")
        run_command(["send_notifications.py"])
    
    elif args.command == "run":
        print("Starting Data Pulse (fetch + notify)...")
        run_command(["fetch_news.py"])
    
    elif args.command == "report":
        print(f"Generating Report for {args.date or 'today'}...")
        cmd = ["generate_report.py"]
        if args.date:
            cmd += ["--date", args.date]
        run_command(cmd)
        
    elif args.command == "server":
        print("Starting API Server & Dashboard...")
        run_command(["api_server.py"])
        
    elif args.command == "status":
        run_command(["api_server.py"]) # Status should just check if online, but for now we'll just run

    elif args.command == "mcp":
        # 1. Force UTF-8 encoding for standard streams
        # This is critical for Windows to handle emojis and special characters correctly
        import sys
        if hasattr(sys.stdin, 'reconfigure'):
            sys.stdin.reconfigure(encoding='utf-8')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        # 2. Smart Stdout Filter
        # This class intercepts ALL writes to stdout.
        # It only allows valid JSON-RPC messages (starting with '{') to pass to the real stdout.
        # Everything else (logs, banners, print debugs) is redirected to stderr.
        class SmartStdout:
            def __init__(self, original_stdout, original_stderr):
                self.stdout = original_stdout
                self.stderr = original_stderr
                self.encoding = 'utf-8'
                self.buffer = original_stdout.buffer
                self.errors = getattr(original_stdout, 'errors', 'strict')
                self.line_buffering = getattr(original_stdout, 'line_buffering', False)
                self.fileno = original_stdout.fileno
                self.isatty = original_stdout.isatty

            def write(self, message):
                try:
                    # Clean check for JSON start
                    # We look at the stripped message to identify content
                    if not message:
                        return
                        
                    stripped = message.strip()
                    if not stripped:
                        # Pass through whitespace if needed, but usually safe to skip or just write
                        return 

                    # MCP Protocol Detection
                    # Simple rule: If it starts with '{', it's likely a JSON message.
                    # FastMCP uses newline-delimited JSON for stdio transport.
                    if stripped.startswith('{'):
                        self.stdout.write(message)
                        self.stdout.flush()
                    else:
                        # Redirect everything else (Rich banners, logs, etc) to stderr
                        # This appears in Claude's logs but doesn't break the connection
                        self.stderr.write(message)
                        self.stderr.flush()
                except Exception:
                    # Failsafe: if anything goes wrong, try to log to stderr
                    try:
                        self.stderr.write(f"[Unexpected Output Error] {message}\n")
                    except:
                        pass

            def flush(self):
                try:
                    self.stdout.flush()
                    self.stderr.flush()
                except:
                    pass
            
            def reconfigure(self, **kwargs):
                pass # Already handled or ignored

        # Apply the filter
        sys.stdout = SmartStdout(sys.stdout, sys.stderr)

        # 3. Environment Setup to discourage TUI libraries from using colors
        os.environ["NO_COLOR"] = "1"
        os.environ["TERM"] = "dumb"

        # 4. Start the Server
        try:
            from mcp_server.server import mcp
            mcp.run(transport=args.mode)
        except ImportError as e:
            sys.stderr.write(f"❌ Failed to load MCP server: {e}\n")
            sys.stderr.write("Ensure fastmcp is installed calls: pip install fastmcp\n")
        except Exception as e:
            sys.stderr.write(f"❌ Server Runtime Error: {e}\n")
        
if __name__ == "__main__":
    main()
