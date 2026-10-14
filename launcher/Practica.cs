// Practica local: servidor en la PC del jugador con los mapas/config del server y bots de AWE.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace CoDUOKit
{
    class MapInfo
    {
        public string Map;        // nombre del .bsp (lo que va en +map)
        public string Name;       // nombre como aparece en el juego
        public List<string> Modes = new List<string>();
        public override string ToString() { return Name; }
    }

    class ModeItem
    {
        public string Code, Label;
        public override string ToString() { return Label; }
    }

    class PracticeChoice
    {
        public string Map, Mode;
        public int BotsAllies, BotsAxis, BotsDm;
        public int Difficulty = 1;      // 0 facil, 1 normal, 2 dificil
        public int Accuracy = 0;        // indice de AccuracyValues (0 = segun la dificultad)
        public static readonly int[] AccuracyValues = { 0, 10, 20, 35, 55, 75 };
        public int AccuracyPercent { get { return AccuracyValues[Math.Max(0, Math.Min(AccuracyValues.Length - 1, Accuracy))]; } }
        public bool IsTeamMode { get { return Mode != "dm"; } }
        public int TotalBots { get { return IsTeamMode ? BotsAllies + BotsAxis : BotsDm; } }
        // vida de los bots: facil 100, normal = la de los jugadores (0), dificil 200
        public int BotHealth { get { return Difficulty == 0 ? 100 : (Difficulty == 2 ? 200 : 0); } }
    }

    class PracticeForm : ShadowForm
    {
        // Orden en que se muestran los modos
        static readonly string[][] Modes = {
            new[] { "tdm", "Duelo a muerte por equipos (TDM)" }, new[] { "dm", "Duelo a muerte - todos contra todos (DM)" },
            new[] { "ctf", "Captura de bandera (CTF)" }, new[] { "bas", "Asalto a la base (BASES)" },
            new[] { "sd", "Busqueda y destruccion (SD)" }, new[] { "hq", "Cuartel general (HQ)" },
            new[] { "bel", "Detras de las lineas (BEL)" }, new[] { "dom", "Dominacion (DOM)" }, new[] { "re", "Recuperacion (RE)" },
        };

        static readonly Color Bg = Color.FromArgb(24, 26, 32);
        static readonly Color Panel = Color.FromArgb(34, 37, 46);
        static readonly Color Accent = Color.FromArgb(91, 99, 241);
        static readonly Color Fg = Color.FromArgb(230, 230, 235);
        static readonly Color Muted = Color.FromArgb(150, 155, 170);

        public PracticeChoice Choice;
        List<MapInfo> allMaps;
        ComboBox cmbMode, cmbMap, cmbDiff, cmbAcc;
        NumericUpDown numAllies, numAxis, numDm;
        Label lblAllies, lblAxis, lblDm, lblInfo, lblCount;

        public PracticeForm(string gameDir, string modDir, PracticeChoice last)
        {
            Text = "Practica local";
            ClientSize = new Size(500, 430);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Bg; ForeColor = Fg; Font = new Font("Segoe UI", 9.5f);

            var title = new Label { Text = "Practica local con bots", Font = new Font("Segoe UI", 13f, FontStyle.Bold), AutoSize = true, Location = new Point(16, 12) };
            var help = new Label { Text = "Servidor en tu PC con los mismos mapas, armas y config del server.\nLos bots recorren el mapa (experimental), te buscan y te disparan.", ForeColor = Muted, Location = new Point(18, 44), Size = new Size(470, 40) };

            var l1 = new Label { Text = "Modo:", AutoSize = true, Location = new Point(18, 100) };
            cmbMode = new ComboBox { Location = new Point(130, 96), Width = 350, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = Panel, ForeColor = Fg, FlatStyle = FlatStyle.Flat };
            var l2 = new Label { Text = "Mapa:", AutoSize = true, Location = new Point(18, 140) };
            cmbMap = new ComboBox { Location = new Point(130, 136), Width = 280, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = Panel, ForeColor = Fg, FlatStyle = FlatStyle.Flat, MaxDropDownItems = 20 };
            lblCount = new Label { ForeColor = Muted, AutoSize = true, Location = new Point(416, 140) };

            // Bots por equipo (modos por equipos) o total (DM)
            lblAllies = new Label { Text = "Bots en Aliados:", AutoSize = true, Location = new Point(18, 182) };
            numAllies = MakeNum(130, 179);
            lblAxis = new Label { Text = "Bots en Eje:", AutoSize = true, Location = new Point(230, 182) };
            numAxis = MakeNum(330, 179);
            lblDm = new Label { Text = "Bots:", AutoSize = true, Location = new Point(18, 182) };
            numDm = MakeNum(130, 179);

            var l4 = new Label { Text = "Dificultad:", AutoSize = true, Location = new Point(18, 224) };
            cmbDiff = new ComboBox { Location = new Point(130, 220), Width = 350, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = Panel, ForeColor = Fg, FlatStyle = FlatStyle.Flat };
            cmbDiff.Items.AddRange(new object[] {
                "Facil - reaccionan lento, fallan mucho, menos vida",
                "Normal - reaccion y punteria media, misma vida que vos",
                "Dificil - reaccionan rapido, punteria alta, mas vida" });

            var l5 = new Label { Text = "Punteria:", AutoSize = true, Location = new Point(18, 264) };
            cmbAcc = new ComboBox { Location = new Point(130, 260), Width = 350, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = Panel, ForeColor = Fg, FlatStyle = FlatStyle.Flat };
            cmbAcc.Items.AddRange(new object[] { "Segun la dificultad", "Muy baja (10% de los tiros pegan)", "Baja (20%)", "Media (35%)", "Alta (55%)", "Muy alta (75%)" });

            lblInfo = new Label { ForeColor = Muted, Location = new Point(18, 300), Size = new Size(470, 54) };

            var ok = new RoundButton { Text = "INICIAR PRACTICA", Location = new Point(280, 370), Size = new Size(200, 42), FlatStyle = FlatStyle.Flat, BackColor = Accent, ForeColor = Color.White, Font = new Font("Segoe UI", 10.5f, FontStyle.Bold) };
            ok.FlatAppearance.BorderSize = 0;
            var cancel = new RoundButton { Text = "Cancelar", Location = new Point(160, 370), Size = new Size(110, 42), FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Color.White, DialogResult = DialogResult.Cancel };
            cancel.FlatAppearance.BorderSize = 0;

            Controls.AddRange(new Control[] { title, help, l1, cmbMode, l2, cmbMap, lblCount, lblAllies, numAllies, lblAxis, numAxis, lblDm, numDm, l4, cmbDiff, l5, cmbAcc, lblInfo, ok, cancel });
            CancelButton = cancel;

            cmbMode.SelectedIndexChanged += delegate { FillMaps(null); UpdateBots(); };
            numAllies.ValueChanged += delegate { UpdateInfo(); };
            numAxis.ValueChanged += delegate { UpdateInfo(); };
            numDm.ValueChanged += delegate { UpdateInfo(); };
            ok.Click += delegate { Accept(); };

            try { allMaps = LoadMaps(gameDir, modDir); }
            catch (Exception ex) { allMaps = new List<MapInfo>(); MessageBox.Show(this, "No pude leer la lista de mapas:\n" + ex.Message); }

            // modos que tienen al menos un mapa
            int selMode = 0;
            foreach (var m in Modes)
            {
                if (!allMaps.Exists(x => x.Modes.Contains(m[0]))) continue;
                if (last != null && m[0] == last.Mode) selMode = cmbMode.Items.Count;
                cmbMode.Items.Add(new ModeItem { Code = m[0], Label = m[1] });
            }
            if (last != null)
            {
                numAllies.Value = Clamp(last.BotsAllies); numAxis.Value = Clamp(last.BotsAxis); numDm.Value = Clamp(last.BotsDm);
                cmbDiff.SelectedIndex = Math.Max(0, Math.Min(2, last.Difficulty));
                cmbAcc.SelectedIndex = Math.Max(0, Math.Min(cmbAcc.Items.Count - 1, last.Accuracy));
            }
            else { numAxis.Value = 4; numDm.Value = 4; cmbDiff.SelectedIndex = 1; cmbAcc.SelectedIndex = 0; }
            if (cmbMode.Items.Count > 0) { cmbMode.SelectedIndex = selMode; FillMaps(last != null ? last.Map : null); }
            UpdateBots();
            UiStyle.DarkCombos(this, Panel, Fg, Accent);
            Ui.Modernize(this, 32, Bg, Color.FromArgb(17, 18, 23), Fg, Color.FromArgb(150, 155, 170), Text, false);
        }

        static decimal Clamp(int v) { return Math.Max(0, Math.Min(16, v)); }

        NumericUpDown MakeNum(int x, int y)
        {
            return new NumericUpDown { Location = new Point(x, y), Width = 60, Minimum = 0, Maximum = 16, BackColor = Panel, ForeColor = Fg };
        }

        string Mode { get { var m = cmbMode.SelectedItem as ModeItem; return m == null ? "" : m.Code; } }

        void FillMaps(string prefer)
        {
            var current = prefer ?? (cmbMap.SelectedItem is MapInfo ? ((MapInfo)cmbMap.SelectedItem).Map : null);
            cmbMap.Items.Clear();
            int sel = 0;
            foreach (var m in allMaps)
            {
                if (!m.Modes.Contains(Mode)) continue;
                if (current != null && string.Equals(m.Map, current, StringComparison.OrdinalIgnoreCase)) sel = cmbMap.Items.Count;
                cmbMap.Items.Add(m);
            }
            if (cmbMap.Items.Count > 0) cmbMap.SelectedIndex = sel;
            lblCount.Text = cmbMap.Items.Count + " mapas";
        }

        void UpdateBots()
        {
            bool team = Mode != "dm";
            lblAllies.Visible = numAllies.Visible = lblAxis.Visible = numAxis.Visible = team;
            lblDm.Visible = numDm.Visible = !team;
            UpdateInfo();
        }

        void UpdateInfo()
        {
            if (Mode == "dm")
                lblInfo.Text = numDm.Value == 0 ? "Sin bots: para recorrer el mapa solo." : "Todos contra todos: vos y " + numDm.Value + " bots.";
            else
                lblInfo.Text = "Al entrar elegis tu equipo. Ejemplo: vos solo contra 5 = Aliados 0, Eje 5, y vos entras en Aliados.\n" +
                               "Aliados: " + numAllies.Value + " bots  -  Eje: " + numAxis.Value + " bots.";
        }

        void Accept()
        {
            var m = cmbMap.SelectedItem as MapInfo;
            if (m == null || Mode == "") { MessageBox.Show(this, "Elegi un modo y un mapa."); return; }
            Choice = new PracticeChoice
            {
                Map = m.Map, Mode = Mode, BotsAllies = (int)numAllies.Value, BotsAxis = (int)numAxis.Value,
                BotsDm = (int)numDm.Value, Difficulty = cmbDiff.SelectedIndex < 0 ? 1 : cmbDiff.SelectedIndex,
                Accuracy = cmbAcc.SelectedIndex < 0 ? 0 : cmbAcc.SelectedIndex
            };
            if (Choice.TotalBots > 16) { MessageBox.Show(this, "Maximo 16 bots en total."); return; }
            DialogResult = DialogResult.OK;
            Close();
        }

        // ---------------- Lista de mapas ----------------
        static string StripColors(string s) { return Regex.Replace(s ?? "", @"\^.", "").Trim(); }

        // Mapas originales sin nombre propio: mp_bocage -> "Bocage", mp_uo_harbor -> "Harbor UO"
        static string Pretty(string map)
        {
            string s = StripColors(map);
            bool uo = false;
            if (s.StartsWith("mp_", StringComparison.OrdinalIgnoreCase)) s = s.Substring(3);
            if (s.StartsWith("uo_", StringComparison.OrdinalIgnoreCase)) { s = s.Substring(3); uo = true; }
            s = CultureInfo.InvariantCulture.TextInfo.ToTitleCase(s.Replace('_', ' ').ToLowerInvariant());
            return uo ? s + " UO" : s;
        }

        // Mapas que se cierran con error de script en todos sus modos (probado 13-10-2026 con el servidor local):
        // errores de los propios mapas o del AWE con sus puntos de aparicion. No se ofrecen en la practica.
        static readonly HashSet<string> Rotos = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
            "mp_cove", "nuenen", "mp_uo_ardennes1944", "townville_ctf", "mp_oxkhov", "ctf_nuenen", "ctf_bazolles",
            "lw_brecourt", "lw_damaucamp", "lw_lars_land4", "uo_tigertown_ctf", "mp_uo_frontline3" };

        // Lista de mapas = CoDmaps.arena del mod (nombres y modos del server) + .arena de cada mapa,
        // solo los .bsp que existen en la PC
        public static List<MapInfo> LoadMaps(string gameDir, string modDir)
        {
            var bsps = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            string arena = null;                       // CoDmaps.arena del mod (lista del server)
            var otherArenas = new List<string>();      // .arena propios de cada mapa
            foreach (var dir in new[] { modDir, "uo", "main" })
            {
                string full = Path.Combine(gameDir, dir);
                if (!Directory.Exists(full)) continue;
                var pk3s = Directory.GetFiles(full, "*.pk3");
                Array.Sort(pk3s, StringComparer.OrdinalIgnoreCase);
                foreach (var pk3 in pk3s)
                {
                    try
                    {
                        using (var z = ZipFile.OpenRead(pk3))
                        {
                            foreach (var e in z.Entries)
                            {
                                string n = e.FullName;
                                if (n.StartsWith("maps/mp/", StringComparison.OrdinalIgnoreCase) && n.EndsWith(".bsp", StringComparison.OrdinalIgnoreCase))
                                    bsps.Add(Path.GetFileNameWithoutExtension(n));
                                if (n.StartsWith("mp/", StringComparison.OrdinalIgnoreCase) && n.EndsWith(".arena", StringComparison.OrdinalIgnoreCase))
                                {
                                    string txt;
                                    using (var r = new StreamReader(e.Open())) txt = r.ReadToEnd();
                                    if (dir == modDir && n.Equals("mp/CoDmaps.arena", StringComparison.OrdinalIgnoreCase)) arena = txt;
                                    else otherArenas.Add(txt);
                                }
                            }
                        }
                    }
                    catch { /* pk3 danado: se ignora */ }
                }
            }

            var list = new List<MapInfo>();
            var all = new List<string>();
            if (arena != null) all.Add(arena);
            all.AddRange(otherArenas);
            string clean = Regex.Replace(string.Join("\n", all.ToArray()), @"//[^\n]*", "");
            foreach (Match b in Regex.Matches(clean, @"\{(.*?)\}", RegexOptions.Singleline))
            {
                var mm = Regex.Match(b.Groups[1].Value, "map\\s+\"([^\"]+)\"", RegexOptions.IgnoreCase);
                var ln = Regex.Match(b.Groups[1].Value, "longname\\s+\"([^\"]*)\"", RegexOptions.IgnoreCase);
                var gt = Regex.Match(b.Groups[1].Value, "gametype\\s+\"([^\"]*)\"", RegexOptions.IgnoreCase);
                if (!mm.Success) continue;
                string map = mm.Groups[1].Value.Trim();
                if (map.EndsWith(".bsp", StringComparison.OrdinalIgnoreCase)) map = map.Substring(0, map.Length - 4);
                if (!bsps.Contains(map)) continue;
                if (Rotos.Contains(map)) continue;
                if (list.Exists(x => x.Map.Equals(map, StringComparison.OrdinalIgnoreCase))) continue;

                string name = ln.Success ? StripColors(ln.Groups[1].Value) : "";
                if (name.Length == 0 || name.Equals(map, StringComparison.OrdinalIgnoreCase) || name.Equals(StripColors(map), StringComparison.OrdinalIgnoreCase))
                    name = Pretty(map);
                var info = new MapInfo { Map = map, Name = name };
                foreach (var g in (gt.Success ? gt.Groups[1].Value : "dm tdm").Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries))
                    if (!info.Modes.Contains(g.ToLowerInvariant())) info.Modes.Add(g.ToLowerInvariant());
                list.Add(info);
            }

            // Nombres repetidos (ej. Carentan original y Carentan UO)
            var seen = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            foreach (var m in list)
                if (list.FindAll(x => x.Name.Equals(m.Name, StringComparison.OrdinalIgnoreCase)).Count > 1 && m.Map.IndexOf("uo_", StringComparison.OrdinalIgnoreCase) >= 0 && m.Name.IndexOf("UO") < 0)
                    m.Name += " UO";
            foreach (var m in list)
            {
                int n;
                seen.TryGetValue(m.Name, out n);
                seen[m.Name] = n + 1;
                if (n > 0) m.Name += " (" + (n + 1) + ")";
            }

            list.Sort((a, b) => string.Compare(a.Name, b.Name, StringComparison.OrdinalIgnoreCase));
            return list;
        }
    }
}
