using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using System.Collections.Generic;

// JSON mini-parser (no external dependency)
using System.Text.Json;

namespace ModMasterGUI
{
    // ── Tiny JSON helper so we don't need Newtonsoft ──────────────────────────
    static class Json
    {
        public static Dictionary<string, object> Parse(string json)
        {
            return JsonSerializer.Deserialize<Dictionary<string, object>>(json)
                   ?? new Dictionary<string, object>();
        }

        public static string Stringify(object obj)
        {
            return JsonSerializer.Serialize(obj);
        }
    }

    // ── Main Form ─────────────────────────────────────────────────────────────
    public class ModMasterForm : Form
    {
        // Controls
        private RichTextBox chatBox;
        private TextBox     inputBox;
        private Button      sendBtn;
        private Button      attachBtn;
        private Label       attachLabel;
        private Label       statusLabel;
        private MenuStrip   menuStrip;

        // State
        private Process pyProcess;
        private bool    busy = false;
        private string  attachedFileName    = null;
        private string  attachedFileContent = null;

        // Groq model list
        static readonly string[] GROQ_MODELS = new[] {
            "groq/llama-3.3-70b-versatile",
            "groq/llama-3.3-70b-specdec",
            "groq/llama-3.1-8b-instant",
            "groq/llama-3.1-70b-versatile",
            "groq/llama-3.2-1b-preview",
            "groq/llama-3.2-3b-preview",
            "groq/llama-3.2-11b-vision-preview",
            "groq/llama-3.2-90b-vision-preview",
            "groq/llama3-8b-8192",
            "groq/llama3-70b-8192",
            "groq/mixtral-8x7b-32768",
            "groq/gemma2-9b-it",
            "groq/gemma-7b-it",
            "groq/deepseek-r1-distill-llama-70b",
            "groq/deepseek-r1-distill-qwen-32b",
            "groq/qwen-qwq-32b",
            "groq/qwen-2.5-coder-32b",
        };
        private string currentModel = "groq/llama-3.3-70b-versatile";

        // Colours — match MODMASTER_GUI.py palette
        static readonly Color BG       = Color.FromArgb(13,  17,  23);
        static readonly Color BG2      = Color.FromArgb(22,  27,  34);
        static readonly Color BORDER   = Color.FromArgb(48,  54,  61);
        static readonly Color CYAN     = Color.FromArgb(121, 192, 255);
        static readonly Color GREEN    = Color.FromArgb(86,  211, 100);
        static readonly Color YELLOW   = Color.FromArgb(227, 179,  65);
        static readonly Color RED      = Color.FromArgb(248,  81,  73);
        static readonly Color DIM      = Color.FromArgb(139, 148, 158);
        static readonly Color FG       = Color.FromArgb(230, 237, 243);
        static readonly Color INPUT_BG = Color.FromArgb(28,  33,  40);

        static readonly Font MONO = new Font("Consolas", 10f);
        static readonly Font UI   = new Font("Segoe UI",  10f);
        static readonly Font BOLD = new Font("Consolas",  10f, FontStyle.Bold);

        public ModMasterForm()
        {
            BuildUI();
            StartPython();
        }

        // ── UI construction ───────────────────────────────────────────────────
        void BuildUI()
        {
            Text        = "MODMASTER v2";
            Size        = new Size(920, 680);
            MinimumSize = new Size(650, 450);
            BackColor   = BG;
            ForeColor   = FG;
            Font        = UI;

            try {
                string ico = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "modmaster.ico");
                if (File.Exists(ico)) Icon = new Icon(ico);
            } catch { }

            // ── Menu ──
            menuStrip = new MenuStrip {
                BackColor = BG2, ForeColor = FG,
                Renderer  = new DarkRenderer()
            };

            var sessionMenu = new ToolStripMenuItem("Session") { ForeColor = FG };
            sessionMenu.DropDownItems.Add(MakeItem("Clear history",   () => SendChat("/clear")));
            sessionMenu.DropDownItems.Add(MakeItem("Show history",    () => SendChat("/history")));
            sessionMenu.DropDownItems.Add(MakeItem("Token usage",     () => SendChat("/tokens")));
            sessionMenu.DropDownItems.Add(new ToolStripSeparator());
            sessionMenu.DropDownItems.Add(MakeItem("Exit",            () => { KillPython(); Application.Exit(); }));

            var cfgMenu = new ToolStripMenuItem("Config") { ForeColor = FG };
            cfgMenu.DropDownItems.Add(MakeItem("Change model…",      ShowModelDialog));
            cfgMenu.DropDownItems.Add(MakeItem("Attach file…",       ShowAttachDialog));
            cfgMenu.DropDownItems.Add(MakeItem("Load instructions…", ShowLoadInstructionsDialog));
            cfgMenu.DropDownItems.Add(MakeItem("Show system prompt", () => SendChat("/system")));
            cfgMenu.DropDownItems.Add(MakeItem("Set API key…",       ShowApiKeyDialog));

            var helpMenu = new ToolStripMenuItem("Help") { ForeColor = FG };
            helpMenu.DropDownItems.Add(MakeItem("Commands", () => SendChat("/help")));

            menuStrip.Items.AddRange(new ToolStripItem[] { sessionMenu, cfgMenu, helpMenu });
            MainMenuStrip = menuStrip;
            Controls.Add(menuStrip);

            // ── Chat area ──
            chatBox = new RichTextBox {
                Dock        = DockStyle.Fill,
                ReadOnly    = true,
                BackColor   = BG,
                ForeColor   = FG,
                Font        = MONO,
                BorderStyle = BorderStyle.None,
                ScrollBars  = RichTextBoxScrollBars.Vertical,
                WordWrap    = true,
                Padding     = new Padding(10),
            };

            var chatPanel = new Panel { Dock = DockStyle.Fill };
            chatPanel.Controls.Add(chatBox);

            // ── Input row ──
            inputBox = new TextBox {
                Dock        = DockStyle.Fill,
                BackColor   = INPUT_BG,
                ForeColor   = FG,
                Font        = MONO,
                BorderStyle = BorderStyle.FixedSingle,
            };
            inputBox.KeyDown += (s, e) => {
                if (e.KeyCode == Keys.Enter && !e.Shift) {
                    e.SuppressKeyPress = true;
                    OnSend();
                }
            };

            sendBtn = new Button {
                Text      = "Send ▶",
                Width     = 96,
                Dock      = DockStyle.Right,
                BackColor = CYAN,
                ForeColor = BG,
                Font      = BOLD,
                FlatStyle = FlatStyle.Flat,
                Cursor    = Cursors.Hand,
            };
            sendBtn.FlatAppearance.BorderSize = 0;
            sendBtn.Click += (s, e) => OnSend();

            // ── Attach button ──
            attachBtn = new Button {
                Text      = "📎",
                Width     = 38,
                Dock      = DockStyle.Right,
                BackColor = BG2,
                ForeColor = YELLOW,
                Font      = new Font("Segoe UI", 13f),
                FlatStyle = FlatStyle.Flat,
                Cursor    = Cursors.Hand,
            };
            // Wire up a real tooltip for the attach button
            var attachTip = new ToolTip();
            attachTip.SetToolTip(attachBtn, "Attach a file (max 100 KB)");
            attachBtn.FlatAppearance.BorderSize = 0;
            attachBtn.FlatAppearance.MouseOverBackColor = BORDER;
            attachBtn.Click += (s, e) => ShowAttachDialog();

            var inputRow = new TableLayoutPanel {
                Dock        = DockStyle.Bottom,
                Height      = 42,
                ColumnCount = 3,
                BackColor   = BG2,
                Padding     = new Padding(8, 4, 8, 4),
            };
            inputRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
            inputRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 44f));
            inputRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 104f));
            inputRow.Controls.Add(inputBox,   0, 0);
            inputRow.Controls.Add(attachBtn,  1, 0);
            inputRow.Controls.Add(sendBtn,    2, 0);

            // ── Attach indicator label ──
            attachLabel = new Label {
                Dock      = DockStyle.Bottom,
                Height    = 20,
                BackColor = BG,
                ForeColor = YELLOW,
                Font      = new Font("Segoe UI", 8.5f),
                Text      = "",
                TextAlign = ContentAlignment.MiddleLeft,
                Padding   = new Padding(10, 0, 0, 0),
                Cursor    = Cursors.Hand,
                Visible   = false,
            };
            attachLabel.Click += (s, e) => ClearAttachment();

            // ── Status bar ──
            statusLabel = new Label {
                Dock      = DockStyle.Bottom,
                Height    = 22,
                BackColor = BG2,
                ForeColor = DIM,
                Font      = UI,
                Text      = "  Starting…",
                TextAlign = ContentAlignment.MiddleLeft,
                Padding   = new Padding(6, 0, 0, 0),
            };

            // ── Master layout ──
            var layout = new TableLayoutPanel {
                Dock        = DockStyle.Fill,
                RowCount    = 2,
                ColumnCount = 1,
            };
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42f));
            layout.Controls.Add(chatPanel, 0, 0);
            layout.Controls.Add(inputRow,  0, 1);

            Controls.Add(layout);
            Controls.Add(attachLabel);
            Controls.Add(statusLabel);

            FormClosing += (s, e) => KillPython();
        }

        ToolStripMenuItem MakeItem(string text, Action action)
        {
            var item = new ToolStripMenuItem(text) { ForeColor = FG, BackColor = BG2 };
            item.Click += (s, e) => action();
            return item;
        }

        // ── Python process lifecycle ──────────────────────────────────────────
        void StartPython()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string script  = Path.Combine(baseDir, "MODMASTER_GUI.py");

            if (!File.Exists(script))
            {
                AppendLine("error", $"Cannot find MODMASTER_GUI.py in: {baseDir}");
                AppendLine("dim",   "Place ModMaster.exe next to MODMASTER_GUI.py and instructions.txt");
                SetStatus("⚠ MODMASTER_GUI.py not found");
                return;
            }

            string python = FindPython();
            if (python == null)
            {
                AppendLine("error", "Python 3 not found on PATH.");
                SetStatus("⚠ Python not found");
                return;
            }

            pyProcess = new Process {
                StartInfo = new ProcessStartInfo {
                    FileName               = python,
                    Arguments              = $"-u \"{script}\" --pipe-mode",
                    WorkingDirectory       = baseDir,
                    UseShellExecute        = false,
                    RedirectStandardInput  = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError  = true,
                    CreateNoWindow         = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding  = Encoding.UTF8,
                },
                EnableRaisingEvents = true,
            };

            pyProcess.OutputDataReceived += OnPyLine;
            pyProcess.ErrorDataReceived  += OnPyError;
            pyProcess.Exited             += OnPyExited;

            try
            {
                pyProcess.Start();
                pyProcess.BeginOutputReadLine();
                pyProcess.BeginErrorReadLine();
            }
            catch (Exception ex)
            {
                AppendLine("error", $"Failed to start Python: {ex.Message}");
            }
        }

        string FindPython()
        {
            foreach (var candidate in new[] { "python", "python3", "py" })
            {
                try
                {
                    var p = Process.Start(new ProcessStartInfo {
                        FileName               = candidate,
                        Arguments              = "--version",
                        UseShellExecute        = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError  = true,
                        CreateNoWindow         = true,
                    });
                    p.WaitForExit(2000);
                    if (p.ExitCode == 0) return candidate;
                }
                catch { }
            }
            return null;
        }

        void KillPython()
        {
            try { if (pyProcess != null && !pyProcess.HasExited) pyProcess.Kill(); }
            catch { }
        }

        // ── Sending messages to Python ────────────────────────────────────────
        void SendJson(object obj)
        {
            try
            {
                string line = Json.Stringify(obj);
                pyProcess.StandardInput.WriteLine(line);
                pyProcess.StandardInput.Flush();
            }
            catch (Exception ex)
            {
                AppendLine("error", $"IPC error: {ex.Message}");
                SetBusy(false);
            }
        }

        void OnSend()
        {
            string text = inputBox.Text.Trim();
            if (string.IsNullOrEmpty(text) || busy) return;
            inputBox.Clear();

            if (text.ToLower() == "quit" || text.ToLower() == "exit")
            {
                KillPython();
                Application.Exit();
                return;
            }

            // Inject attachment if present
            if (attachedFileName != null)
            {
                text = $"[Attached file: {attachedFileName}]\n```\n{attachedFileContent}\n```\n\n{text}";
                ClearAttachment();
            }

            AppendLine("user", text);
            SetBusy(true);
            SendJson(new Dictionary<string, string> { ["type"] = "chat", ["text"] = text });
        }

        void ShowAttachDialog()
        {
            using var ofd = new OpenFileDialog {
                Title  = "Attach a file",
                Filter = "Text / code files|*.txt;*.md;*.py;*.js;*.ts;*.cs;*.json;*.yaml;*.yml;*.csv;*.log;*.xml;*.html;*.css|All files (*.*)|*.*",
            };
            if (ofd.ShowDialog(this) != DialogResult.OK) return;
            try
            {
                var info = new FileInfo(ofd.FileName);
                if (info.Length > 102_400)
                {
                    MessageBox.Show($"File is {info.Length / 1024} KB. Maximum is 100 KB.",
                        "File too large", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                attachedFileName    = Path.GetFileName(ofd.FileName);
                attachedFileContent = File.ReadAllText(ofd.FileName, Encoding.UTF8);
                attachLabel.Text    = $"  📎 {attachedFileName}  ({attachedFileContent.Length:N0} chars)  — click to remove";
                attachLabel.Visible = true;
                AppendLine("dim", $"📎 Attached: {attachedFileName} ({attachedFileContent.Length:N0} chars) — will be sent with your next message.");
            }
            catch (Exception ex)
            {
                AppendLine("error", $"Could not read file: {ex.Message}");
            }
        }

        void ClearAttachment()
        {
            attachedFileName    = null;
            attachedFileContent = null;
            attachLabel.Text    = "";
            attachLabel.Visible = false;
            AppendLine("dim", "Attachment removed.");
        }

        void SendChat(string text)
        {
            inputBox.Text = text;
            OnSend();
        }

        // ── Receiving from Python (JSON lines) ────────────────────────────────
        void OnPyLine(object sender, DataReceivedEventArgs e)
        {
            if (string.IsNullOrEmpty(e.Data)) return;
            string raw = e.Data.Trim();
            if (string.IsNullOrEmpty(raw)) return;

            try
            {
                var msg  = Json.Parse(raw);
                string t = msg.ContainsKey("type") ? msg["type"].ToString() : "unknown";

                Invoke((Action)(() =>
                {
                    switch (t)
                    {
                        case "ready":
                            AppendLine("dim", "MODMASTER v2 — ready. Type /help for commands.");
                            break;

                        case "reply":
                            AppendLine("bot", msg["text"].ToString());
                            break;

                        case "tool":
                            string name   = msg.ContainsKey("name")   ? msg["name"].ToString()   : "?";
                            string result = msg.ContainsKey("result") ? msg["result"].ToString() : "";
                            AppendLine("tool", $"{name} → {result}");
                            break;

                        case "warn":
                            AppendLine("warn", msg["text"].ToString());
                            break;

                        case "error":
                            AppendLine("error", msg["text"].ToString());
                            break;

                        case "status":
                            SetStatus("  " + msg["text"].ToString());
                            break;

                        case "done":
                            SetBusy(false);
                            break;

                        case "pong":
                            // heartbeat reply — ignore
                            break;

                        default:
                            AppendLine("dim", $"[{t}] {raw}");
                            break;
                    }
                }));
            }
            catch
            {
                // Not JSON (startup noise, tracebacks) — show as dim text
                Invoke((Action)(() => AppendLine("dim", raw)));
            }
        }

        void OnPyError(object sender, DataReceivedEventArgs e)
        {
            if (string.IsNullOrEmpty(e.Data)) return;
            // Python stderr = tracebacks / warnings
            Invoke((Action)(() => AppendLine("error", e.Data)));
        }

        void OnPyExited(object sender, EventArgs e)
        {
            Invoke((Action)(() => {
                AppendLine("dim", "— Python process ended —");
                SetStatus("  Python process ended");
                SetBusy(false);
            }));
        }

        // ── Chat display ──────────────────────────────────────────────────────
        void AppendLine(string tag, string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return;
            chatBox.SuspendLayout();

            switch (tag)
            {
                case "user":
                    AppendColored("\nYou\n",   GREEN, bold: true);
                    AppendColored(text + "\n", FG);
                    break;
                case "bot":
                    AppendColored("\nAgent\n", CYAN, bold: true);
                    AppendColored(text + "\n", FG);
                    break;
                case "tool":
                    AppendColored("  ⚙ " + text + "\n", YELLOW);
                    break;
                case "warn":
                    AppendColored("  ⚠ " + text + "\n", YELLOW);
                    break;
                case "error":
                    AppendColored("  ✖ " + text + "\n", RED);
                    break;
                default: // dim / system / info
                    AppendColored(text + "\n", DIM);
                    break;
            }

            chatBox.ResumeLayout();
            chatBox.SelectionStart = chatBox.TextLength;
            chatBox.ScrollToCaret();
        }

        void AppendColored(string text, Color color, bool bold = false)
        {
            chatBox.SelectionStart  = chatBox.TextLength;
            chatBox.SelectionLength = 0;
            chatBox.SelectionColor  = color;
            chatBox.SelectionFont   = bold ? BOLD : MONO;
            chatBox.AppendText(text);
            chatBox.SelectionColor  = FG;
        }

        void SetBusy(bool b)
        {
            busy             = b;
            sendBtn.Enabled  = !b;
            inputBox.Enabled = !b;
            sendBtn.Text     = b ? "…" : "Send ▶";
        }

        void SetStatus(string msg)
        {
            if (statusLabel.InvokeRequired)
                statusLabel.Invoke((Action)(() => statusLabel.Text = msg));
            else
                statusLabel.Text = msg;
        }

        // ── Dialogs ───────────────────────────────────────────────────────────
        void ShowApiKeyDialog()
        {
            using var dlg = new Form {
                Text = "Set GROQ API Key", Size = new Size(440, 168),
                BackColor = BG, ForeColor = FG,
                FormBorderStyle = FormBorderStyle.FixedDialog,
                StartPosition = FormStartPosition.CenterParent,
                MaximizeBox = false,
            };
            var lbl   = new Label  { Text = "GROQ_API_KEY:", AutoSize = true,
                                     Location = new Point(14, 18), ForeColor = FG };
            var entry = new TextBox { Location = new Point(14, 42), Width = 396,
                                      BackColor = INPUT_BG, ForeColor = FG,
                                      BorderStyle = BorderStyle.FixedSingle,
                                      UseSystemPasswordChar = true };
            var btn   = new Button  { Text = "Set Key", Location = new Point(14, 80),
                                      Width = 90, BackColor = CYAN, ForeColor = BG,
                                      FlatStyle = FlatStyle.Flat };
            btn.FlatAppearance.BorderSize = 0;
            btn.Click += (s, e) => {
                string key = entry.Text.Trim();
                if (!string.IsNullOrEmpty(key)) {
                    System.Environment.SetEnvironmentVariable("GROQ_API_KEY", key);
                    // Restart Python so it picks up the new env var
                    KillPython();
                    AppendLine("dim", "API key set — restarting Python…");
                    StartPython();
                    dlg.Close();
                }
            };
            dlg.Controls.AddRange(new Control[] { lbl, entry, btn });
            dlg.ShowDialog(this);
        }

        void ShowModelDialog()
        {
            using var dlg = new Form {
                Text = "Select Model", Size = new Size(520, 220),
                BackColor = BG, ForeColor = FG,
                FormBorderStyle = FormBorderStyle.FixedDialog,
                StartPosition = FormStartPosition.CenterParent,
                MaximizeBox = false,
            };

            var lbl = new Label {
                Text = "Choose a Groq model:", AutoSize = true,
                Location = new Point(14, 16), ForeColor = FG, Font = UI,
            };

            var combo = new ComboBox {
                Location      = new Point(14, 42),
                Width         = 474,
                BackColor     = INPUT_BG,
                ForeColor     = FG,
                Font          = MONO,
                DropDownStyle = ComboBoxStyle.DropDownList,
                FlatStyle     = FlatStyle.Flat,
            };
            combo.Items.AddRange(GROQ_MODELS);
            int idx = Array.IndexOf(GROQ_MODELS, currentModel);
            combo.SelectedIndex = idx >= 0 ? idx : 0;

            var lblCustom = new Label {
                Text = "— or type a custom model string —",
                AutoSize = true, Location = new Point(14, 78),
                ForeColor = DIM, Font = new Font("Segoe UI", 8.5f),
            };

            var customEntry = new TextBox {
                Location    = new Point(14, 100),
                Width       = 474,
                BackColor   = INPUT_BG,
                ForeColor   = FG,
                Font        = MONO,
                BorderStyle = BorderStyle.FixedSingle,
            };

            var btn = new Button {
                Text = "Apply", Location = new Point(14, 136),
                Width = 80, BackColor = CYAN, ForeColor = BG,
                FlatStyle = FlatStyle.Flat,
            };
            btn.FlatAppearance.BorderSize = 0;
            btn.Click += (s, e) => {
                string m = customEntry.Text.Trim();
                if (string.IsNullOrEmpty(m))
                    m = combo.SelectedItem?.ToString() ?? currentModel;
                if (!string.IsNullOrEmpty(m)) {
                    currentModel = m;
                    SendJson(new Dictionary<string, string> {
                        ["type"] = "set_model", ["model"] = m
                    });
                    AppendLine("dim", $"Model → {m}");
                    dlg.Close();
                }
            };
            customEntry.KeyDown += (s, e) => { if (e.KeyCode == Keys.Enter) btn.PerformClick(); };

            dlg.Controls.AddRange(new Control[] { lbl, combo, lblCustom, customEntry, btn });
            dlg.ShowDialog(this);
        }

        void ShowLoadInstructionsDialog()
        {
            using var ofd = new OpenFileDialog {
                Title  = "Load instructions file",
                Filter = "Text files (*.txt)|*.txt|All files (*.*)|*.*",
            };
            if (ofd.ShowDialog(this) != DialogResult.OK) return;
            try
            {
                string content = File.ReadAllText(ofd.FileName, Encoding.UTF8).Trim();
                if (string.IsNullOrEmpty(content)) {
                    MessageBox.Show("The file was empty.", "Empty file", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                SendJson(new Dictionary<string, string> {
                    ["type"] = "set_system", ["prompt"] = content
                });
                AppendLine("dim", $"Loaded '{Path.GetFileName(ofd.FileName)}' ({content.Length:N0} chars). History cleared.");
            }
            catch (Exception ex)
            {
                AppendLine("error", $"Could not load file: {ex.Message}");
            }
        }

        // ── Entry point ───────────────────────────────────────────────────────
        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new ModMasterForm());
        }
    }

    // ── Dark menu renderer ────────────────────────────────────────────────────
    class DarkRenderer : ToolStripProfessionalRenderer
    {
        public DarkRenderer() : base(new DarkColors()) { }

        protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
        {
            Color fill = e.Item.Selected
                ? Color.FromArgb(48, 54, 61)
                : Color.FromArgb(22, 27, 34);
            e.Graphics.FillRectangle(new SolidBrush(fill),
                new Rectangle(Point.Empty, e.Item.Size));
        }
    }

    class DarkColors : ProfessionalColorTable
    {
        static readonly Color BG2 = Color.FromArgb(22, 27, 34);
        public override Color MenuStripGradientBegin         => BG2;
        public override Color MenuStripGradientEnd           => BG2;
        public override Color MenuBorder                     => Color.FromArgb(48, 54, 61);
        public override Color ToolStripDropDownBackground    => BG2;
        public override Color ImageMarginGradientBegin       => BG2;
        public override Color ImageMarginGradientMiddle      => BG2;
        public override Color ImageMarginGradientEnd         => BG2;
    }
}
