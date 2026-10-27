// TOP DEL MES: muestra estadisticas.json (release "stats" del repo), que arma estadisticas\actualizar_estadisticas.py
// leyendo el registro de partidas del servidor cada 30 minutos.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Linq;
using System.Threading;
using System.Windows.Forms;

namespace CoDUOKit
{
    class TopForm : ShadowForm
    {
        static readonly Color Bg = Color.FromArgb(24, 26, 32);
        static readonly Color Panel = Color.FromArgb(34, 37, 46);
        static readonly Color Fg = Color.FromArgb(230, 230, 235);
        static readonly Color Muted = Color.FromArgb(150, 155, 170);
        static readonly Color Gold = Color.FromArgb(232, 190, 60);
        static readonly Color[] Medal = { Color.FromArgb(232, 190, 60), Color.FromArgb(200, 205, 215), Color.FromArgb(205, 127, 50) };

        readonly GitHub gh;
        readonly string myName;
        Dictionary<string, object> meses;
        List<string> orden = new List<string>();
        int idx = -1;
        string actualizado = "";

        Label lblTitle, lblSub, lblPrev, lblMsg;
        Button btnAnt, btnSig, tabBajas, tabCabeza;
        RankPanel pnlKills, pnlWins;
        bool verCabeza;
        const string TextoBajas = "Se reinicia el 1ro de cada mes. Bajas: sin suicidios ni compa\u00F1eros. Ganada: la partida termina (por puntaje o por tiempo) y vos ganaste (DM) o tu equipo gan\u00F3 (TDM, CTF...). Suma todos los servidores. Se actualiza cada 30 minutos.";
        const string TextoCabeza = "Cada impacto en la cabeza cuenta, mate o no (sin compa\u00F1eros de equipo ni a uno mismo). DIO: los que le pegaste a otros. RECIBI\u00D3: los que te pegaron a vos. Suma todos los servidores. Se actualiza cada 30 minutos.";

        public TopForm(GitHub gh, string myName)
        {
            this.gh = gh;
            this.myName = myName ?? "";
            Text = "Top del mes - " + Brand.Name;
            ClientSize = new Size(660, 540);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Bg; ForeColor = Fg;
            Font = new Font("Segoe UI", 9.5f);

            lblTitle = new Label { Text = "TOP DEL MES", Font = new Font("Segoe UI", 17f, FontStyle.Bold), ForeColor = Gold, AutoSize = false, Size = new Size(380, 36), Location = new Point(140, 12), TextAlign = ContentAlignment.MiddleCenter };
            lblSub = new Label { Text = "Cargando...", ForeColor = Muted, AutoSize = false, Size = new Size(620, 20), Location = new Point(20, 50), TextAlign = ContentAlignment.MiddleCenter };
            btnAnt = SmallButton("<  Mes anterior", 20, 16);
            btnSig = SmallButton("Mes siguiente  >", 530, 16);
            btnAnt.Click += delegate { if (idx > 0) { idx--; ShowMonth(); } };
            btnSig.Click += delegate { if (idx < orden.Count - 1) { idx++; ShowMonth(); } };

            // pestanas: bajas y ganadas / tiros a la cabeza
            tabBajas = Tab("BAJAS Y GANADAS", 20);
            tabCabeza = Tab("TIROS A LA CABEZA", 335);
            tabBajas.Click += delegate { verCabeza = false; if (idx >= 0) ShowMonth(); };
            tabCabeza.Click += delegate { verCabeza = true; if (idx >= 0) ShowMonth(); };

            pnlKills = new RankPanel("M\u00C1S BAJAS", "bajas", this.myName) { Location = new Point(20, 116), Size = new Size(305, 330) };
            pnlWins = new RankPanel("M\u00C1S PARTIDAS GANADAS", "ganadas", this.myName) { Location = new Point(335, 116), Size = new Size(305, 330) };

            lblPrev = new Label { ForeColor = Fg, AutoSize = false, Size = new Size(620, 22), Location = new Point(20, 454), TextAlign = ContentAlignment.MiddleCenter };
            lblMsg = new Label
            {
                Text = TextoBajas,
                ForeColor = Muted, AutoSize = false, Size = new Size(530, 48), Location = new Point(20, 480), Font = new Font("Segoe UI", 8.25f)
            };
            var close = new RoundButton { Text = "Cerrar", DialogResult = DialogResult.Cancel, Location = new Point(560, 488), Size = new Size(80, 30), FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg };
            CancelButton = close;
            Controls.AddRange(new Control[] { lblTitle, lblSub, btnAnt, btnSig, tabBajas, tabCabeza, pnlKills, pnlWins, lblPrev, lblMsg, close });
            Ui.Modernize(this, 32, Bg, Color.FromArgb(17, 18, 23), Fg, Muted, Text, false);
            Shown += delegate { LoadStats(); };
        }

        Button Tab(string text, int x)
        {
            var b = new RoundButton { Text = text, Location = new Point(x, 78), Size = new Size(305, 30), FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg, Font = new Font("Segoe UI", 9.5f, FontStyle.Bold) };
            b.FlatAppearance.BorderSize = 0;
            return b;
        }

        Button SmallButton(string text, int x, int y)
        {
            var b = new RoundButton { Text = text, Location = new Point(x, y), Size = new Size(110, 28), FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg, Enabled = false };
            b.FlatAppearance.BorderSize = 0;
            return b;
        }

        void LoadStats()
        {
            var th = new Thread(() =>
            {
                string err = null;
                Dictionary<string, object> data = null;
                try
                {
                    var assets = gh.ListAssets("stats");
                    long id;
                    if (!assets.TryGetValue("estadisticas.json", out id)) throw new Exception("todavia no hay estadisticas publicadas");
                    data = Json.Parse<Dictionary<string, object>>(gh.DownloadText(id));
                }
                catch (Exception ex) { err = ex.Message; }
                try { BeginInvoke(new Action(() => Loaded(data, err))); } catch { }
            });
            th.IsBackground = true;
            th.Start();
        }

        void Loaded(Dictionary<string, object> data, string err)
        {
            if (data == null)
            {
                lblSub.Text = "No pude cargar el top: " + err;
                return;
            }
            meses = data.ContainsKey("meses") ? (Dictionary<string, object>)data["meses"] : new Dictionary<string, object>();
            actualizado = data.ContainsKey("actualizado") ? Convert.ToString(data["actualizado"]) : "";
            orden = meses.Keys.OrderBy(k => k, StringComparer.Ordinal).ToList();
            // mes actual (aunque todavia no tenga partidas)
            string actual = DateTime.UtcNow.AddHours(-3).ToString("yyyy-MM");
            if (!orden.Contains(actual)) orden.Add(actual);
            idx = orden.Count - 1;
            ShowMonth();
        }

        static string MonthName(string ym)
        {
            DateTime d;
            if (!DateTime.TryParseExact(ym + "-01", "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out d)) return ym;
            string n = d.ToString("MMMM yyyy", new CultureInfo("es-AR"));
            return char.ToUpper(n[0]) + n.Substring(1);
        }

        Dictionary<string, object> Month(string ym)
        {
            object o;
            return meses != null && meses.TryGetValue(ym, out o) ? (Dictionary<string, object>)o : null;
        }

        static List<KeyValuePair<string, int>> Ranking(Dictionary<string, object> m, string key)
        {
            var r = new List<KeyValuePair<string, int>>();
            object o;
            if (m != null && m.TryGetValue(key, out o) && o is Dictionary<string, object>)
                foreach (var kv in (Dictionary<string, object>)o) r.Add(new KeyValuePair<string, int>(kv.Key, Convert.ToInt32(kv.Value)));
            r.Sort((a, b) => b.Value != a.Value ? b.Value.CompareTo(a.Value) : string.Compare(a.Key, b.Key, StringComparison.OrdinalIgnoreCase));
            return r;
        }

        void ShowMonth()
        {
            string ym = orden[idx];
            var m = Month(ym);
            lblTitle.Text = "TOP " + MonthName(ym).ToUpper();
            int partidas = m != null && m.ContainsKey("partidas") ? Convert.ToInt32(m["partidas"]) : 0;
            lblSub.Text = partidas + " partidas jugadas en los servidores" + (actualizado != "" ? "   -   actualizado " + actualizado : "");
            // pestana elegida: dorada; la otra, apagada
            tabBajas.BackColor = verCabeza ? Panel : Color.FromArgb(70, 60, 25); tabBajas.ForeColor = verCabeza ? Muted : Gold;
            tabCabeza.BackColor = verCabeza ? Color.FromArgb(70, 60, 25) : Panel; tabCabeza.ForeColor = verCabeza ? Gold : Muted;
            lblMsg.Text = verCabeza ? TextoCabeza : TextoBajas;
            if (verCabeza)
            {
                pnlKills.SetTitle("M\u00C1S TIROS A LA CABEZA (DIO)");
                pnlWins.SetTitle("M\u00C1S TIROS EN LA CABEZA (RECIBI\u00D3)");
                pnlKills.SetData(Ranking(m, "cabeza"));
                pnlWins.SetData(Ranking(m, "cabeza_recibidos"));
            }
            else
            {
                pnlKills.SetTitle("M\u00C1S BAJAS");
                pnlWins.SetTitle("M\u00C1S PARTIDAS GANADAS");
                pnlKills.SetData(Ranking(m, "bajas"));
                pnlWins.SetData(Ranking(m, "ganadas"));
            }
            btnAnt.Enabled = idx > 0;
            btnSig.Enabled = idx < orden.Count - 1;

            // campeones del mes anterior al que se esta viendo
            lblPrev.Text = "";
            if (idx > 0)
            {
                var p = Month(orden[idx - 1]);
                var k = Ranking(p, "bajas");
                var w = Ranking(p, "ganadas");
                if (k.Count > 0 || w.Count > 0)
                    lblPrev.Text = "Campeones de " + MonthName(orden[idx - 1]) + ":   bajas " +
                        (k.Count > 0 ? RankPanel.Strip(k[0].Key) + " (" + k[0].Value + ")" : "-") + "   -   ganadas " +
                        (w.Count > 0 ? RankPanel.Strip(w[0].Key) + " (" + w[0].Value + ")" : "-");
            }
        }

        // Tabla dibujada a mano: puesto, nombre con los colores del juego (^1 rojo...), numero
        class RankPanel : Panel
        {
            string title;
            readonly string unit, me;
            List<KeyValuePair<string, int>> rows = new List<KeyValuePair<string, int>>();
            static readonly Color[] Cod = {
                Color.FromArgb(120, 120, 120), Color.FromArgb(255, 80, 80), Color.FromArgb(90, 220, 90), Color.FromArgb(255, 230, 80),
                Color.FromArgb(100, 140, 255), Color.FromArgb(80, 220, 230), Color.FromArgb(230, 100, 230), Color.FromArgb(235, 235, 235),
                Color.FromArgb(255, 160, 60), Color.FromArgb(160, 160, 160) };

            public RankPanel(string title, string unit, string me)
            {
                this.title = title; this.unit = unit; this.me = me;
                DoubleBuffered = true;
                BackColor = Panel;
            }

            public static string Strip(string s) { return System.Text.RegularExpressions.Regex.Replace(s ?? "", @"\^.", ""); }

            public void SetData(List<KeyValuePair<string, int>> r) { rows = r; Invalidate(); }
            public void SetTitle(string t) { title = t; Invalidate(); }

            protected override void OnPaint(PaintEventArgs e)
            {
                var g = e.Graphics;
                g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
                using (var tf = new Font("Segoe UI", 10.5f, FontStyle.Bold))
                using (var nf = new Font("Segoe UI", 10f))
                using (var bf = new Font("Segoe UI", 10f, FontStyle.Bold))
                {
                    TextRenderer.DrawText(g, title, tf, new Rectangle(0, 8, Width, 22), Gold, TextFormatFlags.HorizontalCenter);
                    if (rows.Count == 0)
                    {
                        TextRenderer.DrawText(g, "Todav\u00EDa nadie este mes", nf, new Rectangle(0, 60, Width, 22), Muted, TextFormatFlags.HorizontalCenter);
                        return;
                    }
                    int y = 40;
                    for (int i = 0; i < rows.Count && i < 10; i++, y += 28)
                    {
                        bool mine = rows[i].Key == me;
                        if (mine)
                            using (var hb = new SolidBrush(Color.FromArgb(55, 60, 85))) g.FillRectangle(hb, 6, y - 3, Width - 12, 26);
                        Color pc = i < 3 ? Medal[i] : Muted;
                        TextRenderer.DrawText(g, (i + 1) + ".", bf, new Point(12, y), pc);
                        DrawCodName(g, rows[i].Key, mine ? bf : nf, 44, y, Width - 120);
                        TextRenderer.DrawText(g, rows[i].Value.ToString(), bf, new Rectangle(Width - 80, y, 68, 22), i < 3 ? pc : Fg, TextFormatFlags.Right);
                    }
                }
            }

            void DrawCodName(Graphics g, string name, Font f, int x, int y, int maxw)
            {
                Color c = Cod[7];
                int start = x;
                for (int i = 0; i < name.Length; i++)
                {
                    if (name[i] == '^' && i + 1 < name.Length && char.IsDigit(name[i + 1]))
                    {
                        c = Cod[name[i + 1] - '0'];
                        i++;
                        continue;
                    }
                    string ch = name[i].ToString();
                    var sz = TextRenderer.MeasureText(g, ch, f, new Size(100, 30), TextFormatFlags.NoPadding);
                    if (x + sz.Width > start + maxw) { TextRenderer.DrawText(g, "...", f, new Point(x, y), Muted, TextFormatFlags.NoPadding); return; }
                    TextRenderer.DrawText(g, ch, f, new Point(x, y), c, TextFormatFlags.NoPadding);
                    x += sz.Width;
                }
            }
        }
    }
}
