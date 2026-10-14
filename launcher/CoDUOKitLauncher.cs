// CoDUOKit Launcher - verifica/actualiza el mod MiMod desde un release privado de GitHub
// y abre Call of Duty: United Offensive con el mod y el nombre del jugador.
// Compilar con build.bat (.NET Framework 4.8, C# 5).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("CoDUOKit Launcher")]
[assembly: System.Reflection.AssemblyProduct("Mi Comunidad")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]

namespace CoDUOKit
{
    class LauncherConfig
    {
        public string owner = "TU_USUARIO";
        public string repo = "mi-mod";
        public string tag = "mod";
        public string token = "";
        public string gameExe = "CoDUOMP.exe";
        public string modDir = "MiMod";
        public string server = "123.45.67.89:28960";   // boton "Entrar al servidor"
        public string title = "";                      // nombre de la comunidad (vacio = el de Brand)
        public string subtitle = "";                   // linea de abajo del titulo (vacio = la de Brand)
    }

    // Textos de la comunidad (los pisa config.json: "title" y "subtitle")
    static class Brand
    {
        public const string Name = "Mi Comunidad";
        public const string Subtitle = "Call of Duty: United Offensive  -  Mi Mod";
    }

    class ManifestFile
    {
        public string path;    // relativo a la carpeta del juego, con "/"
        public string sha256;
        public long size;
        public string asset;   // nombre del asset en el release
        public string mode;    // "sync" (siempre igual) | "ifmissing" (solo si no existe)
    }

    class Manifest
    {
        public string version;
        public List<string> managedDirs; // carpetas donde un .pk3 sobrante se mueve a cuarentena
        public List<ManifestFile> files;
    }

    class Player
    {
        public string name;
        public string display;  // "completa" | "ventana"
        public string fps;      // "no" = ocultar el contador de FPS (por defecto se muestra)
        public string motor;    // "nuevo" = motor mejorado (Open CoD:UO, solo 64 bits)
        public string monitor;  // DeviceName del monitor elegido (ej. \\.\DISPLAY2); vacio = el principal
        public int width;
        public int height;
        public string practiceMap, practiceMode;   // ultima practica elegida
        public int practiceBotsAllies = 0, practiceBotsAxis = 4, practiceBotsDm = 4, practiceDifficulty = 1, practiceAccuracy = 0;
    }

    static class Paths
    {
        // El launcher vive en <juego>\Launcher\CoDUOKitLauncher.exe
        public static string LauncherDir = AppDomain.CurrentDomain.BaseDirectory;
        public static string GameDir = Directory.GetParent(LauncherDir.TrimEnd('\\')).FullName;
        public static string ConfigFile = Path.Combine(LauncherDir, "config.json");
        public static string PlayerFile = Path.Combine(LauncherDir, "player.json");
        public static string ManifestCache = Path.Combine(LauncherDir, "manifest_cache.json");
        public static string LogFile = Path.Combine(LauncherDir, "launcher.log");
    }

    static class Json
    {
        static JavaScriptSerializer S = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        public static T Read<T>(string file) { return S.Deserialize<T>(File.ReadAllText(file, Encoding.UTF8)); }
        public static T Parse<T>(string text) { return S.Deserialize<T>(text); }
        public static void Write(string file, object o) { File.WriteAllText(file, S.Serialize(o), new UTF8Encoding(false)); }
    }

    class GitHub
    {
        LauncherConfig cfg;
        public GitHub(LauncherConfig c) { cfg = c; }

        HttpWebRequest Req(string url, string accept, bool auth)
        {
            var r = (HttpWebRequest)WebRequest.Create(url);
            r.UserAgent = "CoDUOKitLauncher";
            r.Accept = accept;
            r.Timeout = 30000;
            r.ReadWriteTimeout = 60000;
            r.AllowAutoRedirect = false;
            if (auth && !string.IsNullOrEmpty(cfg.token))
                r.Headers["Authorization"] = "Bearer " + cfg.token;
            return r;
        }

        // Devuelve nombre de asset -> id
        public Dictionary<string, long> ListAssets() { return ListAssets(cfg.tag); }

        // tag "stats": el release con estadisticas.json (TOP DEL MES)
        public Dictionary<string, long> ListAssets(string tag)
        {
            string url = string.Format("https://api.github.com/repos/{0}/{1}/releases/tags/{2}", cfg.owner, cfg.repo, tag);
            using (var resp = (HttpWebResponse)Req(url, "application/vnd.github+json", true).GetResponse())
            using (var sr = new StreamReader(resp.GetResponseStream()))
            {
                var rel = Json.Parse<Dictionary<string, object>>(sr.ReadToEnd());
                var result = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
                foreach (var a in (System.Collections.ArrayList)rel["assets"])
                {
                    var d = (Dictionary<string, object>)a;
                    result[(string)d["name"]] = Convert.ToInt64(d["id"]);
                }
                return result;
            }
        }

        // Descarga un asset a un archivo. Sigue la redireccion SIN token (va a otro dominio).
        public void Download(long assetId, string dest, Action<long> progress)
        {
            string url = string.Format("https://api.github.com/repos/{0}/{1}/releases/assets/{2}", cfg.owner, cfg.repo, assetId);
            HttpWebResponse resp = (HttpWebResponse)Req(url, "application/octet-stream", true).GetResponse();
            for (int hops = 0; hops < 5 && ((int)resp.StatusCode >= 300 && (int)resp.StatusCode < 400); hops++)
            {
                string loc = resp.Headers["Location"];
                resp.Close();
                resp = (HttpWebResponse)Req(loc, "application/octet-stream", false).GetResponse();
            }
            using (resp)
            using (var input = resp.GetResponseStream())
            using (var output = File.Create(dest))
            {
                var buf = new byte[1 << 16];
                long total = 0;
                int n;
                while ((n = input.Read(buf, 0, buf.Length)) > 0)
                {
                    output.Write(buf, 0, n);
                    total += n;
                    if (progress != null) progress(total);
                }
            }
        }

        public string DownloadText(long assetId)
        {
            string tmp = Path.GetTempFileName();
            try { Download(assetId, tmp, null); return File.ReadAllText(tmp, Encoding.UTF8); }
            finally { File.Delete(tmp); }
        }
    }

    class MainForm : ShadowForm
    {
        static readonly Color Bg = Color.FromArgb(24, 26, 32);
        static readonly Color Panel = Color.FromArgb(34, 37, 46);
        static readonly Color Accent = Color.FromArgb(91, 99, 241);
        static readonly Color Fg = Color.FromArgb(230, 230, 235);
        static readonly Color Muted = Color.FromArgb(150, 155, 170);

        LauncherConfig cfg;
        Player player;
        Label lblName, lblStatus, lblTitle, lblSub;
        SlimBar bar;
        TextBox log;
        Button btnPlay, btnPractice, btnServer, btnKeys, btnName, btnVerify, btnFolder;
        ComboBox cmbDisplay, cmbRes, cmbMonitor;
        CheckBox chkFps, chkMotor;
        bool loadingDisplay;
        volatile bool busy;

        public MainForm()
        {
            Text = Brand.Name + " - Launcher";
            ClientSize = new Size(684, 430);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Bg;
            ForeColor = Fg;
            Font = new Font("Segoe UI", 9.5f);
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            lblTitle = new Label { Text = Brand.Name + "!", Font = new Font("Segoe UI", 20f, FontStyle.Bold), AutoSize = true, Location = new Point(20, 14) };
            lblSub = new Label { Text = Brand.Subtitle, ForeColor = Muted, AutoSize = true, Location = new Point(24, 56) };
            lblName = new Label { AutoSize = true, Location = new Point(24, 86), Font = new Font("Segoe UI", 10.5f) };
            var lblDisp = new Label { Text = "Pantalla:", AutoSize = true, Location = new Point(24, 120) };
            cmbDisplay = new ComboBox { Location = new Point(92, 116), Width = 150, DropDownStyle = ComboBoxStyle.DropDownList, FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg };
            cmbDisplay.Items.AddRange(new object[] { "Pantalla completa", "Ventana" });
            var lblRes = new Label { Text = "Resolucion:", AutoSize = true, Location = new Point(262, 120) };
            cmbRes = new ComboBox { Location = new Point(344, 116), Width = 130, DropDownStyle = ComboBoxStyle.DropDownList, FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg };
            chkFps = new CheckBox { Text = "Mostrar FPS", AutoSize = true, Location = new Point(492, 119), ForeColor = Fg };
            chkFps.CheckedChanged += delegate { SaveDisplay(); };
            Controls.Add(chkFps);
            // Motor mejorado: solo en Windows de 64 bits (los archivos del motor nuevo son x64)
            chkMotor = new CheckBox { Text = "Motor mejorado (graficos)", AutoSize = true, Location = new Point(472, 40), ForeColor = Fg, Visible = Environment.Is64BitOperatingSystem };
            chkMotor.CheckedChanged += delegate { SaveDisplay(); };
            new ToolTip().SetToolTip(chkMotor, "Usa el motor nuevo Open CoD:UO (mejor imagen y pantallas anchas).\nDestildalo para volver al juego original.");
            Controls.Add(chkMotor);
            // Monitor donde se abre el juego (solo si hay mas de uno)
            var lblMon = new Label { Text = "Monitor:", AutoSize = true, Location = new Point(262, 88), Visible = Screen.AllScreens.Length > 1 };
            cmbMonitor = new ComboBox { Location = new Point(326, 84), Width = 130, DropDownStyle = ComboBoxStyle.DropDownList, FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg, Visible = Screen.AllScreens.Length > 1 };
            for (int i = 0; i < Screen.AllScreens.Length; i++)
                cmbMonitor.Items.Add((i + 1) + (Screen.AllScreens[i].Primary ? " (principal)" : ""));
            cmbMonitor.SelectedIndexChanged += delegate { if (!loadingDisplay) { SaveDisplay(); LoadDisplay(); } };
            new ToolTip().SetToolTip(cmbMonitor, "Con el Motor mejorado el juego se abre en el monitor elegido.\nEl juego original siempre se abre en el monitor principal de Windows.");
            Controls.Add(lblMon); Controls.Add(cmbMonitor);

            lblStatus = new Label { AutoSize = false, Size = new Size(636, 22), Location = new Point(24, 152), ForeColor = Muted };
            bar = new SlimBar { Location = new Point(24, 178), Size = new Size(636, 10) };
            log = new TextBox { Location = new Point(24, 202), Size = new Size(636, 156), Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.None, BackColor = Panel, ForeColor = Fg, BorderStyle = BorderStyle.None, Font = new Font("Consolas", 9f) };

            btnPlay = MakeButton("JUGAR", 24, true);
            btnPlay.Size = new Size(130, 44);
            btnPlay.Font = new Font("Segoe UI", 12f, FontStyle.Bold);
            btnPractice = MakeButton("PRACTICA", 160, false);
            btnPractice.Size = new Size(112, 44);
            btnPractice.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            btnPractice.BackColor = Color.FromArgb(46, 125, 80);
            btnKeys = MakeButton("Teclas", 278, false);
            btnName = MakeButton("Cambiar nombre", 372, false);
            btnVerify = MakeButton("Reparar", 474, false);
            btnFolder = MakeButton("Abrir carpeta", 576, false);
            btnKeys.Width = 88; btnName.Width = 96; btnVerify.Width = 96; btnFolder.Width = 84;

            btnServer = new RoundButton { Text = "ENTRAR AL SERVIDOR", Location = new Point(470, 70), Size = new Size(190, 38), BackColor = Color.FromArgb(214, 124, 30), ForeColor = Color.White, Font = new Font("Segoe UI", 10f, FontStyle.Bold), Radius = 12 };
            btnServer.Click += delegate { Launch(" +connect " + (string.IsNullOrEmpty(cfg.server) ? "123.45.67.89:28960" : cfg.server)); };
            Controls.Add(btnServer);

            // TOP DEL MES (estadisticas del servidor: bajas y partidas ganadas, se reinicia cada mes)
            var btnTop = new RoundButton { Text = "TOP DEL MES", Location = new Point(470, 6), Size = new Size(190, 30), BackColor = Color.FromArgb(58, 50, 22), ForeColor = Color.FromArgb(240, 200, 70), Font = new Font("Segoe UI", 9.5f, FontStyle.Bold), Radius = 15, BorderColor = Color.FromArgb(232, 190, 60) };
            btnTop.Click += delegate
            {
                if (cfg == null) return;
                using (var f = new TopForm(new GitHub(cfg), player != null ? player.name : "")) f.ShowDialog(this);
            };
            Controls.Add(btnTop);

            btnPlay.Click += delegate { Play(); };
            btnPractice.Click += delegate { Practice(); };
            btnKeys.Click += delegate { OpenKeys(); };
            btnName.Click += delegate { AskName(); };
            btnVerify.Click += delegate { Repair(); };
            btnFolder.Click += delegate { Process.Start("explorer.exe", "\"" + Paths.GameDir + "\""); };
            cmbDisplay.SelectedIndexChanged += delegate { SaveDisplay(); };
            cmbRes.SelectedIndexChanged += delegate { SaveDisplay(); };

            Controls.AddRange(new Control[] { lblTitle, lblSub, lblName, lblDisp, cmbDisplay, lblRes, cmbRes, lblStatus, bar, UiStyle.InRoundPanel(log, Panel), btnPlay, btnPractice, btnKeys, btnName, btnVerify, btnFolder });
            UiStyle.DarkCombos(this, Panel, Fg, Accent);
            // ventana moderna: sin la barra de Windows, barra propia, bordes redondeados (Ui.cs)
            Ui.Modernize(this, 34, Bg, Color.FromArgb(17, 18, 23), Fg, Muted, Text, true);
            Shown += delegate { OnStart(); };
        }

        Button MakeButton(string text, int x, bool primary)
        {
            var b = new RoundButton { Text = text, Location = new Point(x, 372), Size = new Size(122, 44), BackColor = primary ? Accent : Panel, ForeColor = Color.White };
            b.FlatAppearance.BorderSize = 0;
            return b;
        }

        void Log(string msg)
        {
            string line = DateTime.Now.ToString("HH:mm:ss") + "  " + msg;
            try { File.AppendAllText(Paths.LogFile, DateTime.Now.ToString("yyyy-MM-dd ") + line + Environment.NewLine); } catch { }
            if (InvokeRequired) { BeginInvoke(new Action(() => Log2(line))); } else Log2(line);
        }
        void Log2(string line) { log.AppendText(line + Environment.NewLine); }

        void Status(string msg, int pct)
        {
            Action a = delegate { lblStatus.Text = msg; if (pct >= 0) bar.Value = Math.Max(0, Math.Min(100, pct)); };
            if (InvokeRequired) BeginInvoke(a); else a();
        }

        void SetBusy(bool b)
        {
            Action a = delegate { busy = b; btnPlay.Enabled = !b; btnPractice.Enabled = !b; btnServer.Enabled = !b; btnVerify.Enabled = !b; btnName.Enabled = !b; };
            if (InvokeRequired) BeginInvoke(a); else a();
        }

        void OnStart()
        {
            // restos de una auto-actualizacion anterior
            try { foreach (var v in Directory.GetFiles(Paths.LauncherDir, "*.viejo")) File.Delete(v); } catch { }
            try { foreach (var v in Directory.GetFiles(Paths.LauncherDir, "*.descargando")) File.Delete(v); } catch { }

            try
            {
                cfg = File.Exists(Paths.ConfigFile) ? Json.Read<LauncherConfig>(Paths.ConfigFile) : new LauncherConfig();
            }
            catch (Exception ex) { cfg = new LauncherConfig(); Log("config.json invalido: " + ex.Message); }
            // nombre de la comunidad desde config.json (si esta)
            if (!string.IsNullOrEmpty(cfg.title)) { Text = cfg.title + " - Launcher"; lblTitle.Text = cfg.title + "!"; Invalidate(true); }
            if (!string.IsNullOrEmpty(cfg.subtitle)) lblSub.Text = cfg.subtitle;
            // sin servidor configurado (paquete para jugar offline): no mostrar "ENTRAR AL SERVIDOR"
            if (string.IsNullOrEmpty(cfg.server)) btnServer.Visible = false;

            if (!File.Exists(Path.Combine(Paths.GameDir, cfg.gameExe)))
            {
                MessageBox.Show(this, "No encuentro " + cfg.gameExe + " en:\n" + Paths.GameDir + "\n\nEl launcher tiene que estar en la carpeta Launcher dentro del juego.", Brand.Name, MessageBoxButtons.OK, MessageBoxIcon.Error);
                Close();
                return;
            }

            try { player = File.Exists(Paths.PlayerFile) ? Json.Read<Player>(Paths.PlayerFile) : null; } catch { player = null; }
            if (player != null) SyncFromGame(File.GetLastWriteTimeUtc(Paths.PlayerFile));
            if (player == null || string.IsNullOrEmpty(player.name)) AskName();
            ShowName();
            LoadDisplay();
            ActiveControl = btnPlay;
            StartVerify();
        }

        string ModCfg { get { return Path.Combine(Paths.GameDir, cfg.modDir, "uoconfig_mp.cfg"); } }

        // ---- Pantalla ----
        void LoadDisplay()
        {
            loadingDisplay = true;
            cmbMonitor.SelectedIndex = MonitorIndex();
            var scr = GameScreen().Bounds.Size;
            var list = new List<Size>();
            int[,] common = { { 800, 600 }, { 1024, 768 }, { 1280, 720 }, { 1280, 800 }, { 1280, 1024 }, { 1366, 768 }, { 1440, 900 }, { 1600, 900 }, { 1600, 1024 }, { 1680, 1050 }, { 1920, 1080 }, { 2560, 1440 }, { 3840, 2160 } };
            for (int i = 0; i < common.GetLength(0); i++)
                if (common[i, 0] <= scr.Width && common[i, 1] <= scr.Height) list.Add(new Size(common[i, 0], common[i, 1]));
            if (!list.Contains(scr)) list.Add(scr);

            int w = player.width, h = player.height;
            if (w <= 0 || h <= 0)
            {
                // Primera vez: tomar la resolucion que ya tiene configurada el juego, o la del monitor
                var gc = GameConfig.Load(ModCfg);
                int.TryParse(gc.GetCvar("r_customwidth"), out w);
                int.TryParse(gc.GetCvar("r_customheight"), out h);
                if (w <= 0 || h <= 0 || w > scr.Width || h > scr.Height) { w = scr.Width; h = scr.Height; }
            }
            var cur = new Size(w, h);
            if (!list.Contains(cur)) list.Add(cur);
            list.Sort((a, b) => a.Width != b.Width ? a.Width.CompareTo(b.Width) : a.Height.CompareTo(b.Height));

            cmbRes.Items.Clear();
            foreach (var s in list) cmbRes.Items.Add(s.Width + " x " + s.Height);
            cmbRes.SelectedIndex = list.IndexOf(cur);
            cmbDisplay.SelectedIndex = player.display == "ventana" ? 1 : 0;
            chkFps.Checked = player.fps != "no";
            chkMotor.Checked = player.motor == "nuevo" && Environment.Is64BitOperatingSystem;
            loadingDisplay = false;
            SaveDisplay();
        }

        void SaveDisplay()
        {
            if (loadingDisplay || player == null || cmbRes.SelectedItem == null) return;
            string[] p = cmbRes.SelectedItem.ToString().Split('x');
            player.width = int.Parse(p[0].Trim());
            player.height = int.Parse(p[1].Trim());
            player.display = cmbDisplay.SelectedIndex == 1 ? "ventana" : "completa";
            player.fps = chkFps.Checked ? "si" : "no";
            player.motor = chkMotor.Checked ? "nuevo" : "original";
            if (cmbMonitor.SelectedIndex >= 0 && cmbMonitor.SelectedIndex < Screen.AllScreens.Length)
                player.monitor = Screen.AllScreens[cmbMonitor.SelectedIndex].DeviceName;
            try { Json.Write(Paths.PlayerFile, player); } catch { }
        }

        // Indice del monitor elegido en Screen.AllScreens (el motor mejorado usa el mismo orden en r_display)
        int MonitorIndex()
        {
            var all = Screen.AllScreens;
            if (player != null && !string.IsNullOrEmpty(player.monitor))
                for (int i = 0; i < all.Length; i++) if (all[i].DeviceName == player.monitor) return i;
            for (int i = 0; i < all.Length; i++) if (all[i].Primary) return i;
            return 0;
        }

        Screen GameScreen() { return Screen.AllScreens[MonitorIndex()]; }

        void OpenKeys()
        {
            if (!File.Exists(ModCfg))
            {
                MessageBox.Show(this, "Todavia no existe la configuracion del juego:\n" + ModCfg + "\n\nAbri el juego una vez con JUGAR y despues vas a poder cambiar las teclas.", "Teclas");
                return;
            }
            using (var f = new KeyBindForm(ModCfg)) f.ShowDialog(this);
            SaveDisplay();  // el launcher escribio la config: que player.json quede igual de nuevo (ver SyncFromGame)
        }

        // ---- Sincronizar con el juego: gana donde se cambio por ultima vez ----
        // Tabla r_mode del juego (el original llega al 12, el motor mejorado agrega los panoramicos hasta el 24)
        static readonly int[,] VidModes = { { 320, 240 }, { 400, 300 }, { 512, 384 }, { 640, 480 }, { 800, 600 }, { 960, 720 }, { 1024, 768 }, { 1152, 864 }, { 1280, 1024 }, { 1600, 1200 }, { 2048, 1536 }, { 856, 480 }, { 1920, 1200 },
            { 1280, 720 }, { 1280, 800 }, { 1366, 768 }, { 1440, 900 }, { 1600, 900 }, { 1680, 1050 }, { 1920, 1080 }, { 2560, 1440 }, { 2560, 1600 }, { 2880, 1800 }, { 3024, 1964 }, { 3456, 2234 } };

        // Si el juego guardo su config despues de la ultima vez que el launcher guardo la suya y hay diferencias
        // (resolucion, pantalla, FPS o nombre cambiados dentro del juego), el launcher toma los valores del juego.
        // Si se cambio en el launcher, player.json es mas nuevo y al jugar el launcher se los pasa al juego.
        void SyncFromGame(DateTime playerTime)
        {
            try
            {
                if (!File.Exists(ModCfg) || File.GetLastWriteTimeUtc(ModCfg) <= playerTime) return;
                var gc = GameConfig.Load(ModCfg);
                var cambios = new List<string>();

                int mode, w = 0, h = 0;
                if (int.TryParse(gc.GetCvar("r_mode"), out mode))
                {
                    if (mode == -1) { int.TryParse(gc.GetCvar("r_customwidth"), out w); int.TryParse(gc.GetCvar("r_customheight"), out h); }
                    else if (mode >= 0 && mode < VidModes.GetLength(0)) { w = VidModes[mode, 0]; h = VidModes[mode, 1]; }
                }
                if (w > 0 && h > 0 && (w != player.width || h != player.height)) { player.width = w; player.height = h; cambios.Add("resolucion " + w + " x " + h); }

                string fs = gc.GetCvar("r_fullscreen");
                if (fs == "0" || fs == "1")
                {
                    string disp = fs == "0" ? "ventana" : "completa";
                    if (disp != (player.display == "ventana" ? "ventana" : "completa")) { player.display = disp; cambios.Add(fs == "0" ? "ventana" : "pantalla completa"); }
                }

                string fps = gc.GetCvar("cg_drawFPS");
                if (fps != "")
                {
                    string v = fps == "0" ? "no" : "si";
                    if (v != (player.fps == "no" ? "no" : "si")) { player.fps = v; cambios.Add(v == "si" ? "mostrar FPS" : "ocultar FPS"); }
                }

                string name = gc.GetCvar("name");
                if (name != "" && name != player.name) { player.name = name; cambios.Add("nombre " + StripColors(name)); }

                if (cambios.Count > 0) Log("Tomado de la configuracion del juego: " + string.Join(", ", cambios.ToArray()));
            }
            catch (Exception ex) { Log("No pude leer la configuracion del juego: " + ex.Message); }
        }

        void ShowName()
        {
            lblName.Text = "Jugador:  " + (player != null && !string.IsNullOrEmpty(player.name) ? StripColors(player.name) : "(sin nombre)");
        }

        static string StripColors(string s)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < s.Length; i++)
            {
                if (s[i] == '^' && i + 1 < s.Length) { i++; continue; }
                sb.Append(s[i]);
            }
            return sb.ToString();
        }

        void AskName()
        {
            using (var f = new Form())
            {
                f.Text = "Nombre del personaje";
                f.ClientSize = new Size(380, 150);
                f.FormBorderStyle = FormBorderStyle.FixedDialog;
                f.StartPosition = FormStartPosition.CenterParent;
                f.MaximizeBox = false; f.MinimizeBox = false;
                f.BackColor = Bg; f.ForeColor = Fg; f.Font = Font;
                var l = new Label { Text = "Escribi el nombre con el que vas a jugar\n(se pueden usar colores: ^1rojo ^2verde ^3amarillo ^5celeste ^7blanco)", AutoSize = true, Location = new Point(14, 12) };
                var t = new TextBox { Location = new Point(16, 58), Width = 346, MaxLength = 31, Text = player != null ? player.name : "" };
                var ok = new Button { Text = "Guardar", DialogResult = DialogResult.OK, Location = new Point(262, 100), Size = new Size(100, 32), FlatStyle = FlatStyle.Flat, BackColor = Accent, ForeColor = Color.White };
                ok.FlatAppearance.BorderSize = 0;
                f.Controls.AddRange(new Control[] { l, t, ok });
                f.AcceptButton = ok;
                while (true)
                {
                    if (f.ShowDialog(this) != DialogResult.OK)
                    {
                        if (player != null && !string.IsNullOrEmpty(player.name)) return;
                        continue; // la primera vez el nombre es obligatorio
                    }
                    string n = t.Text.Replace("\"", "").Replace(";", "").Trim();
                    if (StripColors(n).Trim().Length == 0) { MessageBox.Show(f, "El nombre no puede estar vacio."); continue; }
                    if (player == null) player = new Player();
                    player.name = n;
                    try { Json.Write(Paths.PlayerFile, player); } catch (Exception ex) { Log("No pude guardar el nombre: " + ex.Message); }
                    Log("Nombre guardado: " + StripColors(n));
                    break;
                }
            }
            ShowName();
        }

        // Reparar: borra la marca de Modo Seguro, opcionalmente restablece el video y vuelve a verificar/bajar todo
        void Repair()
        {
            if (busy) return;
            try
            {
                string marca = Path.Combine(Paths.GameDir, "__CoDUOMP");
                if (File.Exists(marca)) { File.SetAttributes(marca, FileAttributes.Normal); File.Delete(marca); Log("Reparar: marca de Modo Seguro borrada."); }
            }
            catch (Exception ex) { Log("Reparar: no pude borrar __CoDUOMP: " + ex.Message); }

            var r = MessageBox.Show(this,
                "Voy a revisar y volver a bajar los archivos que falten o esten danados.\n\n" +
                "Ademas, si se ve mal el juego (pantalla negra, textos raros, resolucion rara):\n" +
                "Queres RESTABLECER LA CONFIGURACION DE VIDEO?\n" +
                "(No toca tus teclas, sensibilidad ni nombre. Se guarda una copia.)",
                "Reparar", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
            if (r == DialogResult.Cancel) return;
            if (r == DialogResult.Yes) ResetVideo();
            FixLanguageInCfg(GameLanguage());
            StartVerify();
        }

        // Saca del uoconfig_mp.cfg del mod solo las opciones de video (r_* y vid_*); el juego vuelve a sus valores por defecto
        void ResetVideo()
        {
            string f = ModCfg;
            try
            {
                if (!File.Exists(f)) { Log("Reparar: no hay configuracion del juego para restablecer."); return; }
                string bak = f + ".antes_de_reparar";
                File.Copy(f, bak, true);
                var keep = new List<string>();
                int quitadas = 0;
                foreach (var l in File.ReadAllLines(f, Encoding.Default))
                {
                    string t = l.TrimStart();
                    if (t.StartsWith("seta r_", StringComparison.OrdinalIgnoreCase) || t.StartsWith("seta vid_", StringComparison.OrdinalIgnoreCase)) { quitadas++; continue; }
                    keep.Add(l);
                }
                File.WriteAllLines(f, keep.ToArray(), Encoding.Default);
                Log("Reparar: configuracion de video restablecida (" + quitadas + " opciones). Copia en " + Path.GetFileName(bak));
            }
            catch (Exception ex) { Log("Reparar: no pude restablecer el video: " + ex.Message); }
        }

        void StartVerify()
        {
            if (busy) return;
            // modo sin actualizaciones (paquete offline): sin repo configurado no se intenta GitHub
            if (cfg == null || string.IsNullOrEmpty(cfg.owner) || string.IsNullOrEmpty(cfg.repo))
            {
                Log("Modo sin actualizaciones: no hay repositorio configurado en config.json.");
                Status("Listo para jugar (sin actualizaciones automaticas).", 100);
                return;
            }
            SetBusy(true);
            var th = new Thread(() =>
            {
                try { Verify(); }
                catch (Exception ex) { Log("ERROR: " + ex.Message); Status("Error durante la verificacion (ver detalle abajo). Podes jugar igual.", 0); }
                finally { SetBusy(false); }
            });
            th.IsBackground = true;
            th.Start();
        }

        static string Sha256(string file, Action<long> progress)
        {
            using (var sha = SHA256.Create())
            using (var fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
            {
                var buf = new byte[1 << 20];
                int n; long done = 0;
                while ((n = fs.Read(buf, 0, buf.Length)) > 0)
                {
                    sha.TransformBlock(buf, 0, n, null, 0);
                    done += n;
                    if (progress != null) progress(done);
                }
                sha.TransformFinalBlock(buf, 0, 0);
                return BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
            }
        }

        void Verify()
        {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            var gh = new GitHub(cfg);
            Manifest man = null;
            Dictionary<string, long> assets = null;

            Status("Buscando actualizaciones...", 0);
            try
            {
                assets = gh.ListAssets();
                long mid;
                if (!assets.TryGetValue("manifest.json", out mid)) throw new Exception("el release no tiene manifest.json");
                string text = gh.DownloadText(mid);
                man = Json.Parse<Manifest>(text);
                File.WriteAllText(Paths.ManifestCache, text, new UTF8Encoding(false));
                Log("Version publicada: " + man.version);
            }
            catch (Exception ex)
            {
                Log("Sin conexion con GitHub (" + ex.Message + ")");
                assets = null;
                if (File.Exists(Paths.ManifestCache))
                {
                    man = Json.Read<Manifest>(Paths.ManifestCache);
                    Log("Verificando contra la ultima lista guardada (" + man.version + ")");
                }
                else
                {
                    Status("Sin conexion y sin lista guardada: no se verifico nada. Podes jugar igual.", 0);
                    return;
                }
            }

            // 1) Calcular que archivos hay que bajar
            long totalBytes = 0;
            foreach (var f in man.files) if (f.mode != "ifmissing") totalBytes += f.size;
            long hashed = 0;
            var toFetch = new List<ManifestFile>();
            foreach (var f in man.files)
            {
                string local = Path.Combine(Paths.GameDir, f.path.Replace('/', '\\'));
                if (f.mode == "ifmissing")
                {
                    if (!File.Exists(local)) toFetch.Add(f);
                    continue;
                }
                string name = Path.GetFileName(local);
                if (!File.Exists(local)) { Log("Falta: " + f.path); toFetch.Add(f); hashed += f.size; continue; }
                if (new FileInfo(local).Length != f.size) { Log("Distinto (tamano): " + f.path); toFetch.Add(f); hashed += f.size; continue; }
                long baseDone = hashed;
                string h = Sha256(local, d => Status("Verificando " + name + "...", (int)((baseDone + d) * 100 / Math.Max(1, totalBytes))));
                hashed += f.size;
                if (!string.Equals(h, f.sha256, StringComparison.OrdinalIgnoreCase)) { Log("Distinto (contenido): " + f.path); toFetch.Add(f); }
            }

            // 2) Mover a cuarentena los .pk3 que sobran (con sv_pure el server te rechaza)
            var wanted = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var f in man.files) wanted.Add(f.path.Replace('/', '\\'));
            if (man.managedDirs != null)
            {
                foreach (var dir in man.managedDirs)
                {
                    string full = Path.Combine(Paths.GameDir, dir.Replace('/', '\\'));
                    if (!Directory.Exists(full)) continue;
                    foreach (var pk3 in Directory.GetFiles(full, "*.pk3"))
                    {
                        string rel = pk3.Substring(Paths.GameDir.Length).TrimStart('\\');
                        if (wanted.Contains(rel)) continue;
                        string q = Path.Combine(full, "_cuarentena");
                        Directory.CreateDirectory(q);
                        string dest = Path.Combine(q, Path.GetFileName(pk3));
                        if (File.Exists(dest)) File.Delete(dest);
                        File.Move(pk3, dest);
                        Log("Sobraba, movido a _cuarentena: " + rel);
                    }
                }
            }

            if (toFetch.Count == 0)
            {
                Status("Todo al dia. Listo para jugar.", 100);
                Log("Archivos verificados: todo correcto.");
                SelfUpdate();
                return;
            }
            if (assets == null)
            {
                Status("Hay " + toFetch.Count + " archivo(s) con diferencias pero no hay conexion para corregirlos.", 0);
                return;
            }

            // 3) Descargar y reemplazar
            long need = 0; foreach (var f in toFetch) need += f.size;
            long got = 0;
            foreach (var f in toFetch)
            {
                long id;
                if (!assets.TryGetValue(f.asset, out id)) { Log("ERROR: el release no tiene " + f.asset); continue; }
                string local = Path.Combine(Paths.GameDir, f.path.Replace('/', '\\'));
                Directory.CreateDirectory(Path.GetDirectoryName(local));
                string tmp = local + ".descargando";
                long baseGot = got;
                string fname = Path.GetFileName(local);
                gh.Download(id, tmp, d => Status(string.Format("Descargando {0}  ({1:N0} / {2:N0} MB)", fname, (baseGot + d) / 1048576, need / 1048576), (int)((baseGot + d) * 100 / Math.Max(1, need))));
                string h = Sha256(tmp, null);
                if (!string.Equals(h, f.sha256, StringComparison.OrdinalIgnoreCase))
                {
                    File.Delete(tmp);
                    Log("ERROR: " + f.path + " se descargo danado, se reintenta en la proxima verificacion.");
                    continue;
                }
                try
                {
                    if (File.Exists(local)) File.Delete(local);
                    File.Move(tmp, local);
                    got += f.size;
                    Log("Actualizado: " + f.path);
                }
                catch (Exception ex)
                {
                    // un archivo que falla no corta la verificacion del resto
                    Log("ERROR al reemplazar " + f.path + ": " + ex.Message);
                    try { if (File.Exists(tmp)) File.Delete(tmp); } catch { }
                }
            }
            Status("Actualizacion terminada. Listo para jugar.", 100);
            Log("Actualizacion terminada.");
            SelfUpdate();
        }

        // El launcher se publica como Launcher\CoDUOKitLauncher.exe.nuevo (un archivo comun para la sincronizacion,
        // asi los launchers viejos no intentan pisar el .exe que esta corriendo). Si es distinto al que corre,
        // se renombra el actual a .viejo, se pone el nuevo en su lugar y se reinicia.
        void SelfUpdate()
        {
            string self = Application.ExecutablePath;
            string nuevo = self + ".nuevo";
            try
            {
                if (!File.Exists(nuevo)) return;
                if (string.Equals(Sha256(nuevo, null), Sha256(self, null), StringComparison.OrdinalIgnoreCase)) return;
                string viejo = self + ".viejo";
                if (File.Exists(viejo)) File.Delete(viejo);
                File.Move(self, viejo);
                File.Copy(nuevo, self);
                selfUpdated = true;
                Log("Launcher actualizado a una version nueva.");
            }
            catch (Exception ex) { Log("No pude actualizar el launcher: " + ex.Message); return; }

            if (selfUpdated)
            {
                Status("Launcher actualizado: reiniciando...", 100);
                BeginInvoke(new Action(() =>
                {
                    try { Process.Start(new ProcessStartInfo(Application.ExecutablePath) { WorkingDirectory = Paths.LauncherDir, UseShellExecute = true }); } catch { }
                    Close();
                }));
            }
        }

        bool selfUpdated;

        void Play()
        {
            Launch("");
        }

        void Practice()
        {
            if (!File.Exists(Path.Combine(Paths.GameDir, cfg.modDir, "practica.cfg")))
            {
                MessageBox.Show(this, "Falta practica.cfg en " + cfg.modDir + ".\nToca \"Verificar archivos\" para bajarlo.", "Practica");
                return;
            }
            PracticeChoice last = null;
            if (player != null && !string.IsNullOrEmpty(player.practiceMode))
                last = new PracticeChoice { Map = player.practiceMap, Mode = player.practiceMode, BotsAllies = player.practiceBotsAllies,
                                            BotsAxis = player.practiceBotsAxis, BotsDm = player.practiceBotsDm, Difficulty = player.practiceDifficulty,
                                            Accuracy = player.practiceAccuracy };
            using (var f = new PracticeForm(Paths.GameDir, cfg.modDir, last))
            {
                if (f.ShowDialog(this) != DialogResult.OK || f.Choice == null) return;
                var c = f.Choice;
                player.practiceMap = c.Map; player.practiceMode = c.Mode; player.practiceBotsAllies = c.BotsAllies;
                player.practiceBotsAxis = c.BotsAxis; player.practiceBotsDm = c.BotsDm; player.practiceDifficulty = c.Difficulty;
                player.practiceAccuracy = c.Accuracy;
                try { Json.Write(Paths.PlayerFile, player); } catch { }
                // Servidor DEDICADO oculto en la PC (solo 127.0.0.1) + el juego conectandose a el.
                // (Como "servidor + jugador" en un solo proceso, algunos mapas como miniharbor cierran el juego.)
                // awe_bots_* los usa el _awe_bots.gsc de zzzzzz_kit_practica.pk3
                string server = "+set dedicated 1 +set net_ip 127.0.0.1 +set net_port " + PracticePort +
                       " +set fs_game " + cfg.modDir + " +set sv_pure 0 +set logfile 0 +set sv_maxclients " + (c.TotalBots + 4) +
                       " +exec practica.cfg +set g_gametype " + c.Mode + " +set awe_bots " + c.TotalBots +
                       " +set awe_bots_allies " + (c.IsTeamMode ? c.BotsAllies : 0) +
                       " +set awe_bots_axis " + (c.IsTeamMode ? c.BotsAxis : 0) +
                       " +set awe_bots_health " + c.BotHealth + " +set awe_bots_skill " + c.Difficulty +
                       " +set awe_bots_accuracy " + c.AccuracyPercent + " +map " + c.Map;
                Launch(" +connect 127.0.0.1:" + PracticePort, server);
            }
        }

        const int PracticePort = 28961;

        // Pregunta "getstatus" al servidor local hasta que responda (responde recien cuando termino de cargar el mapa)
        static bool WaitForLocalServer(int port, int timeoutMs, Process server)
        {
            var sw = Stopwatch.StartNew();
            byte[] q = new byte[] { 0xFF, 0xFF, 0xFF, 0xFF }.Concat(Encoding.ASCII.GetBytes("getstatus")).ToArray();
            while (sw.ElapsedMilliseconds < timeoutMs)
            {
                if (server != null && server.HasExited) return false;
                try
                {
                    using (var u = new System.Net.Sockets.UdpClient())
                    {
                        u.Client.ReceiveTimeout = 700;
                        u.Send(q, q.Length, "127.0.0.1", port);
                        var ep = new IPEndPoint(IPAddress.Any, 0);
                        var r = u.Receive(ref ep);
                        if (r.Length > 4 && Encoding.ASCII.GetString(r).Contains("mapname")) return true;
                    }
                }
                catch { }
                Application.DoEvents();
                Thread.Sleep(300);
            }
            return false;
        }

        static readonly string[] Idiomas = { "english", "french", "german", "italian", "spanish", "british", "russian", "polish", "korean", "taiwanese", "japanese", "chinese", "thai" };

        // Numero de cl_language segun localization.txt del juego (la instalacion es en espanol = 4)
        string GameLanguage()
        {
            try
            {
                string f = Path.Combine(Paths.GameDir, "localization.txt");
                if (File.Exists(f))
                {
                    int i = Array.IndexOf(Idiomas, File.ReadAllLines(f)[0].Trim().ToLowerInvariant());
                    if (i >= 0) return i.ToString();
                }
            }
            catch { }
            return "4";
        }

        // Deja "seta cl_language" correcto en el uoconfig_mp.cfg del mod
        void FixLanguageInCfg(string lang)
        {
            SetCfgCvars(new[] { "cl_language", lang }, true);
        }

        // Escribe "seta <cvar> <valor>" en el uoconfig_mp.cfg del mod (pares cvar, valor)
        void SetCfgCvars(string[] pares, bool logLang)
        {
            string f = ModCfg;
            try
            {
                if (!File.Exists(f)) return;
                var lines = new List<string>(File.ReadAllLines(f, Encoding.Default));
                bool changed = false;
                for (int i = 0; i + 1 < pares.Length; i += 2)
                {
                    string cv = pares[i];
                    string want = "seta " + cv + " \"" + pares[i + 1] + "\"";
                    int idx = lines.FindIndex(l => l.TrimStart().StartsWith("seta " + cv + " ", StringComparison.OrdinalIgnoreCase));
                    if (idx >= 0 && lines[idx].Trim() == want) continue;
                    if (logLang && idx >= 0) Log("Idioma del juego corregido: " + lines[idx].Trim() + " -> " + want);
                    if (idx >= 0) lines[idx] = want; else lines.Add(want);
                    changed = true;
                }
                if (changed) File.WriteAllLines(f, lines.ToArray(), Encoding.Default);
            }
            catch (Exception ex) { Log("No pude escribir la configuracion del juego: " + ex.Message); }
        }

        // ---- Motor mejorado (Open CoD:UO) ----
        // El launcher baja el motor nuevo a Launcher\motor\nuevo y al jugar pone esos archivos o los originales
        // (guardados en Launcher\motor\original la primera vez) segun la casilla.
        static readonly string[] MotorFiles = { "CoDUOMP.exe", @"uo\uo_cgame_mp_x86.dll", @"uo\uo_game_mp_x86.dll", @"uo\uo_ui_mp_x86.dll" };
        static string MotorDir(string which) { return Path.Combine(Paths.LauncherDir, "motor", which); }

        static bool SameFile(string a, string b)
        {
            if (!File.Exists(a) || !File.Exists(b)) return false;
            if (new FileInfo(a).Length != new FileInfo(b).Length) return false;
            return Sha256(a) == Sha256(b);
        }

        static string Sha256(string f)
        {
            using (var s = File.OpenRead(f)) using (var h = SHA256.Create())
                return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "");
        }

        bool UsingNewMotor()
        {
            return player.motor == "nuevo" && Environment.Is64BitOperatingSystem && SameFile(Path.Combine(Paths.GameDir, MotorFiles[0]), Path.Combine(MotorDir("nuevo"), MotorFiles[0]));
        }

        // Devuelve false si no se pudo dejar el motor pedido (el juego sigue con lo que tenia)
        bool ApplyMotor()
        {
            bool nuevo = player.motor == "nuevo" && Environment.Is64BitOperatingSystem;
            string dN = MotorDir("nuevo"), dO = MotorDir("original");
            try
            {
                if (nuevo)
                {
                    foreach (var f in MotorFiles)
                        if (!File.Exists(Path.Combine(dN, f))) { Log("Motor mejorado: falta " + f + " (toca Reparar). Se usa el original."); return false; }
                    foreach (var f in MotorFiles)
                    {
                        string g = Path.Combine(Paths.GameDir, f), n = Path.Combine(dN, f), o = Path.Combine(dO, f);
                        if (SameFile(g, n)) continue;
                        if (!File.Exists(o) && File.Exists(g)) { Directory.CreateDirectory(Path.GetDirectoryName(o)); File.Copy(g, o); }
                        File.Copy(n, g, true);
                        Log("Motor mejorado: puesto " + f);
                    }
                }
                else
                {
                    foreach (var f in MotorFiles)
                    {
                        string g = Path.Combine(Paths.GameDir, f), o = Path.Combine(dO, f);
                        if (!File.Exists(o) || SameFile(g, o)) continue;
                        File.Copy(o, g, true);
                        Log("Motor original: restaurado " + f);
                    }
                }
                return true;
            }
            catch (Exception ex)
            {
                Log("No pude cambiar el motor (esta el juego abierto?): " + ex.Message);
                MessageBox.Show(this, "No pude cambiar el motor del juego:\n" + ex.Message + "\n\nCerra el juego y proba de nuevo.", Brand.Name, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }
        }

        // Si el juego se cierra mal deja el monitor con el brillo del juego (todo blanco): lo vuelve a lo normal
        [System.Runtime.InteropServices.DllImport("gdi32.dll", CharSet = System.Runtime.InteropServices.CharSet.Auto)]
        static extern IntPtr CreateDC(string drv, string dev, string o, IntPtr i);
        [System.Runtime.InteropServices.DllImport("gdi32.dll")]
        static extern bool DeleteDC(IntPtr dc);
        [System.Runtime.InteropServices.DllImport("gdi32.dll")]
        static extern bool SetDeviceGammaRamp(IntPtr dc, ushort[] ramp);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool SetForegroundWindow(IntPtr h);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool AllowSetForegroundWindow(int pid);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool ShowWindow(IntPtr h, int cmd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern IntPtr GetForegroundWindow();
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern void keybd_event(byte vk, byte scan, int flags, IntPtr extra);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern void SwitchToThisWindow(IntPtr h, bool altTab);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
        [System.Runtime.InteropServices.DllImport("kernel32.dll")]
        static extern uint GetCurrentThreadId();
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool AttachThreadInput(uint a, uint b, bool attach);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool BringWindowToTop(IntPtr h);

        // Windows no deja que un programa le pase el foco a otro (SetForegroundWindow falla en silencio), y en la
        // practica el permiso de foco se lo lleva el servidor oculto, que arranca primero. Se "engancha" la entrada
        // de este hilo con la de la ventana que tiene el foco y con la del juego, y asi el cambio si se permite.
        static bool BringToFront(IntPtr h)
        {
            if (GetForegroundWindow() == h) return true;
            ShowWindow(h, 9);                       // SW_RESTORE
            uint me = GetCurrentThreadId();
            uint fgThread = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero);
            uint gameThread = GetWindowThreadProcessId(h, IntPtr.Zero);
            bool a1 = fgThread != 0 && fgThread != me && AttachThreadInput(me, fgThread, true);
            bool a2 = gameThread != 0 && gameThread != me && AttachThreadInput(me, gameThread, true);
            keybd_event(0x12, 0, 0, IntPtr.Zero);   // Alt abajo/arriba: tambien habilita el cambio de foco
            keybd_event(0x12, 0, 2, IntPtr.Zero);
            BringWindowToTop(h);
            SetForegroundWindow(h);
            if (a2) AttachThreadInput(me, gameThread, false);
            if (a1) AttachThreadInput(me, fgThread, false);
            if (GetForegroundWindow() != h) SwitchToThisWindow(h, true);
            return GetForegroundWindow() == h;
        }

        // En la practica el servidor oculto arranca primero y la ventana del juego puede quedar sin foco:
        // con el motor mejorado (raw input) el mouse no llega al juego y el cursor de los menus queda "bloqueado".
        // Espera a que aparezca la ventana del juego y la pone al frente.
        // (el juego puede recrear su ventana al iniciar el video: se vuelve a enfocar cada ventana nueva
        // hasta que la misma queda estable 8 s)
        void FocusGame(Process game)
        {
            IntPtr last = IntPtr.Zero;
            int stable = 0;
            bool hidden = false;
            for (int i = 0; i < 120 && stable < 16; i++)    // hasta 60 s
            {
                try
                {
                    if (game.HasExited) break;
                    game.Refresh();
                    IntPtr h = game.MainWindowHandle;
                    if (h != IntPtr.Zero)
                    {
                        if (h != last) { last = h; stable = 0; Log("Ventana del juego: " + h + " (al frente: " + (GetForegroundWindow() == h) + ")"); }
                        // recien con la ventana del juego al frente se oculta el launcher (asi el foco pasa al juego)
                        if (BringToFront(h)) stable++;
                        if (!hidden) { hidden = true; BeginInvoke(new Action(Hide)); }
                    }
                }
                catch (Exception ex) { Log("Foco: " + ex.Message); break; }
                Thread.Sleep(500);
            }
            Log("Foco del juego: " + (last != IntPtr.Zero && GetForegroundWindow() == last ? "si" : "NO") + " (" + stable + ")");
            if (!hidden) BeginInvoke(new Action(Hide));
        }

        static void RestoreGamma()
        {
            var ramp = new ushort[768];
            for (int i = 0; i < 256; i++) ramp[i] = ramp[256 + i] = ramp[512 + i] = (ushort)(i * 257);
            foreach (var s in Screen.AllScreens)
            {
                try
                {
                    IntPtr dc = CreateDC(s.DeviceName, null, null, IntPtr.Zero);
                    if (dc == IntPtr.Zero) continue;
                    SetDeviceGammaRamp(dc, ramp);
                    DeleteDC(dc);
                }
                catch { }
            }
        }

        void Launch(string extraArgs)
        {
            Launch(extraArgs, null);
        }

        void Launch(string extraArgs, string serverArgs)
        {
            if (player == null || string.IsNullOrEmpty(player.name)) { AskName(); if (player == null) return; }
            string exe = Path.Combine(Paths.GameDir, cfg.gameExe);
            SaveDisplay();
            // logfile 2: la consola se escribe al instante en MiMod\console_mp.log (sirve para diagnosticar cuelgues)
            string args = "+set fs_game " + cfg.modDir + " +set name \"" + player.name + "\" +set logfile 2";
            // Texturas en calidad completa: el mod trae texturas DDS sin mipmaps y con r_picmip > 0
            // el juego las achica en el procesador al cargar cada mapa (cargas de 20+ segundos).
            args += " +set r_picmip 0 +set r_picmip2 0";
            // Vsync apagado: con r_swapInterval 1 cada redibujado de la pantalla de carga espera al monitor
            // y la carga de un mapa pasa de ~3,5 s a ~19 s (medido 12-10-2026). com_maxfps 85 ya limita los FPS.
            args += " +set r_swapInterval 0";
            // Contador de FPS del juego (arriba a la derecha)
            args += " +set cg_drawFPS " + (player.fps == "no" ? "0" : "1");
            // Idioma: si el juego detecta otra placa de video aplica la "configuracion optima" y vuelve cl_language
            // a ingles; como solo estan los textos en espanol, aparecen EXE_CONNECTINGTO y similares.
            string lang = GameLanguage();
            FixLanguageInCfg(lang);
            args += " +set cl_language " + lang;
            if (player.width > 0 && player.height > 0)
                args += " +set r_mode -1 +set r_customwidth " + player.width + " +set r_customheight " + player.height;
            if (player.display == "ventana")
            {
                var wa = GameScreen().WorkingArea;
                // centrada en el monitor elegido (puede tener coordenadas negativas si esta a la izquierda del principal)
                // El motor mejorado toma vid_xpos/vid_ypos relativos al monitor de r_display; el original, absolutos
                // (y siempre en el monitor principal: el juego viejo no puede abrirse en otro).
                bool rel = player.motor == "nuevo" && Environment.Is64BitOperatingSystem;
                int x = (rel ? 0 : wa.Left) + Math.Max(0, (wa.Width - player.width) / 2);
                int y = (rel ? wa.Top - GameScreen().Bounds.Top : wa.Top) + Math.Max(0, (wa.Height - player.height - 30) / 2);
                args += " +set r_fullscreen 0 +set vid_xpos " + x + " +set vid_ypos " + y;
            }
            else args += " +set r_fullscreen 1";
            // Lo que elige el launcher tambien queda en la config del juego (asi coinciden aunque el juego se cierre mal)
            if (player.width > 0 && player.height > 0)
                SetCfgCvars(new[] { "r_mode", "-1", "r_customwidth", player.width.ToString(), "r_customheight", player.height.ToString(),
                                    "r_fullscreen", player.display == "ventana" ? "0" : "1", "cg_drawFPS", player.fps == "no" ? "0" : "1", "name", player.name }, false);
            ApplyMotor();
            // Motor mejorado: brillo aplicado dentro del juego (no cambia el brillo del monitor)
            if (UsingNewMotor()) args += " +set r_gammaMode 2 +set r_display " + MonitorIndex();
            args += extraArgs;

            // El juego crea el archivo oculto __CoDUOMP al arrancar y lo borra al salir bien.
            // Si quedo de un cierre anterior, pregunta "Ejecutar en Modo Seguro" y eso desconfigura todo.
            try
            {
                string marca = Path.Combine(Paths.GameDir, "__CoDUOMP");
                if (File.Exists(marca))
                {
                    File.SetAttributes(marca, FileAttributes.Normal);
                    File.Delete(marca);
                    Log("Se borro la marca de cierre incorrecto (evita el cartel de Modo Seguro).");
                }
            }
            catch (Exception ex) { Log("No pude borrar __CoDUOMP: " + ex.Message); }

            Process server = null;
            try
            {
                if (serverArgs != null)
                {
                    Log("Servidor de practica: " + serverArgs);
                    // UseShellExecute = true: Windows le puso al juego modo compatibilidad XP (WINXPSP2) y asi
                    // CreateProcess directo falla con "requiere elevacion"; via shell arranca normal (igual que JUGAR).
                    var spsi = new ProcessStartInfo(exe, serverArgs);
                    spsi.WorkingDirectory = Paths.GameDir;
                    spsi.UseShellExecute = true;
                    spsi.WindowStyle = ProcessWindowStyle.Hidden;
                    server = Process.Start(spsi);
                    // Esperar a que el servidor termine de cargar el mapa (si no, el menu de equipo no responde un rato)
                    Status("Preparando la practica (cargando mapa y bots)...", 50);
                    Cursor = Cursors.WaitCursor;
                    bool ready = WaitForLocalServer(PracticePort, 60000, server);
                    Cursor = Cursors.Default;
                    if (!ready) Log("El servidor de practica tardo mucho en responder; se abre el juego igual.");
                    else Thread.Sleep(1500);    // que entren los bots
                }

                Log("Iniciando: " + args);
                var psi = new ProcessStartInfo(exe, args);
                psi.WorkingDirectory = Paths.GameDir;
                psi.UseShellExecute = true;
                AllowSetForegroundWindow(-1);   // ASFW_ANY: que el juego pueda tomar el foco al abrir
                var game = Process.Start(psi);
                Log("Juego iniciado.");

                // El launcher queda oculto hasta que se cierra el juego: restaura el brillo del monitor
                // y, en la practica, apaga el servidor local. (Se oculta en FocusGame, cuando el juego ya tiene el foco.)
                var srv = server;
                var th = new Thread(() =>
                {
                    FocusGame(game);
                    try { game.WaitForExit(); } catch { }
                    try { if (srv != null && !srv.HasExited) srv.Kill(); } catch { }
                    RestoreGamma();
                    BeginInvoke(new Action(Close));
                });
                th.IsBackground = true;
                th.Start();
            }
            catch (Exception ex)
            {
                try { if (server != null && !server.HasExited) server.Kill(); } catch { }
                Show();
                MessageBox.Show(this, "No se pudo abrir el juego:\n" + ex.Message, Brand.Name, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }
}
