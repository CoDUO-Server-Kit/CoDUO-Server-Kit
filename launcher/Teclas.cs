// Editor de teclas: lee y escribe los "bind" de MiMod\uoconfig_mp.cfg
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace CoDUOKit
{
    // Config del juego: lineas originales + binds (tecla -> comando)
    class GameConfig
    {
        public string File;
        public List<string> Lines = new List<string>();
        public Dictionary<string, string> Binds = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public List<string> BindOrder = new List<string>();

        public static GameConfig Load(string file)
        {
            var gc = new GameConfig { File = file };
            if (!System.IO.File.Exists(file)) return gc;
            foreach (var raw in System.IO.File.ReadAllLines(file, Encoding.Default))
            {
                gc.Lines.Add(raw);
                string key, cmd;
                if (ParseBind(raw, out key, out cmd)) gc.SetBind(key, cmd);
            }
            return gc;
        }

        // bind KEY "comando"   |   bind KEY comando
        static bool ParseBind(string line, out string key, out string cmd)
        {
            key = cmd = null;
            string t = line.Trim();
            if (!t.StartsWith("bind ", StringComparison.OrdinalIgnoreCase) && !t.StartsWith("bind\t", StringComparison.OrdinalIgnoreCase)) return false;
            t = t.Substring(4).Trim();
            int sp = t.IndexOfAny(new[] { ' ', '\t' });
            if (sp < 0) return false;
            key = t.Substring(0, sp).Trim('"');
            cmd = t.Substring(sp).Trim();
            if (cmd.Length >= 2 && cmd[0] == '"' && cmd[cmd.Length - 1] == '"') cmd = cmd.Substring(1, cmd.Length - 2);
            return key.Length > 0;
        }

        public void SetBind(string key, string cmd)
        {
            key = key.ToUpperInvariant();
            if (!Binds.ContainsKey(key)) BindOrder.Add(key);
            Binds[key] = cmd;
        }

        public void RemoveBind(string key)
        {
            key = key.ToUpperInvariant();
            Binds.Remove(key);
            BindOrder.Remove(key);
        }

        public List<string> KeysFor(string cmd)
        {
            var r = new List<string>();
            foreach (var k in BindOrder)
                if (string.Equals(Binds[k].Trim(), cmd, StringComparison.OrdinalIgnoreCase)) r.Add(k);
            return r;
        }

        public string GetCvar(string name)
        {
            foreach (var l in Lines)
            {
                var p = l.Trim().Split(new[] { ' ', '\t' }, 3, StringSplitOptions.RemoveEmptyEntries);
                if (p.Length == 3 && (p[0] == "seta" || p[0] == "set") && string.Equals(p[1], name, StringComparison.OrdinalIgnoreCase))
                    return p[2].Trim('"');
            }
            return "";
        }

        public void Save()
        {
            // Reemplaza todas las lineas bind por las actuales, justo despues de "unbindall"
            var outp = new List<string>();
            bool inserted = false;
            Action addBinds = delegate
            {
                foreach (var k in BindOrder) outp.Add("bind " + k + " \"" + Binds[k] + "\"");
                inserted = true;
            };
            foreach (var l in Lines)
            {
                string k, c;
                if (ParseBind(l, out k, out c)) continue;
                outp.Add(l);
                if (!inserted && l.Trim().Equals("unbindall", StringComparison.OrdinalIgnoreCase)) addBinds();
            }
            if (!inserted)
            {
                int at = outp.Count > 0 && outp[0].StartsWith("//") ? 1 : 0;
                var tmp = outp; outp = new List<string>();
                for (int i = 0; i < at; i++) outp.Add(tmp[i]);
                outp.Add("unbindall");
                addBinds();
                for (int i = at; i < tmp.Count; i++) outp.Add(tmp[i]);
            }
            string bak = File + ".bak";
            if (System.IO.File.Exists(File)) System.IO.File.Copy(File, bak, true);
            System.IO.File.WriteAllLines(File, outp.ToArray(), Encoding.Default);
            Lines = outp;
        }
    }

    class KeyBindForm : ShadowForm, IMessageFilter
    {
        // Comandos tomados de la tabla de controles del propio juego (uo_uix86.dll)
        static readonly string[][] Actions = {
            new[] { "#Movimiento" },
            new[] { "+forward", "Adelante" },
            new[] { "+back", "Atras" },
            new[] { "+moveleft", "Izquierda" },
            new[] { "+moveright", "Derecha" },
            new[] { "+gostand", "Saltar / pararse" },
            new[] { "gocrouch", "Agacharse" },
            new[] { "goprone", "Cuerpo a tierra" },
            new[] { "+sprint", "Correr (sprint)" },
            new[] { "+leanleft", "Asomarse a la izquierda" },
            new[] { "+leanright", "Asomarse a la derecha" },
            new[] { "#Combate" },
            new[] { "+attack", "Disparar" },
            new[] { "toggle cl_run", "Apuntar con mira (alternar)" },
            new[] { "+speed", "Apuntar con mira (mantener)" },
            new[] { "+reload", "Recargar" },
            new[] { "+melee", "Golpe / culatazo" },
            new[] { "+activate", "Usar / interactuar" },
            new[] { "weapalt", "Modo de disparo / arma alternativa" },
            new[] { "#Armas" },
            new[] { "weaponslot primary", "Arma principal" },
            new[] { "weaponslot primaryb", "Arma secundaria" },
            new[] { "weaponslot pistol", "Pistola" },
            new[] { "weaponslot grenade", "Granada" },
            new[] { "weaponslot smokegrenade", "Granada de humo" },
            new[] { "weaponslot satchel", "Carga explosiva" },
            new[] { "weaponslot binocular", "Binoculares" },
            new[] { "weapnext", "Arma siguiente" },
            new[] { "weapprev", "Arma anterior" },
            new[] { "#Multijugador" },
            new[] { "+scores", "Ver puntajes" },
            new[] { "messagemode", "Chat general" },
            new[] { "messagemode2", "Chat de equipo" },
            new[] { "mp_QuickMessage", "Chat rapido" },
            new[] { "mp_quickmap", "Mapa" },
            new[] { "vote yes", "Votar SI" },
            new[] { "vote no", "Votar NO" },
            new[] { "screenshotJPEG", "Captura de pantalla" },
        };

        // Teclas por defecto del juego (default_mp.cfg)
        static readonly string[][] Defaults = {
            new[] { "W", "+forward" }, new[] { "S", "+back" }, new[] { "A", "+moveleft" }, new[] { "D", "+moveright" },
            new[] { "ALT", "+sprint" }, new[] { "Q", "+leanleft" }, new[] { "E", "+leanright" }, new[] { "SHIFT", "+melee" },
            new[] { "MOUSE1", "+attack" }, new[] { "MOUSE2", "toggle cl_run" }, new[] { "M", "weapalt" }, new[] { "F", "+activate" },
            new[] { "R", "+reload" }, new[] { "SPACE", "+gostand" }, new[] { "CTRL", "goprone" }, new[] { "C", "gocrouch" },
            new[] { "MWHEELDOWN", "weapnext" }, new[] { "MWHEELUP", "weapprev" }, new[] { "1", "weaponslot primary" },
            new[] { "2", "weaponslot primaryb" }, new[] { "3", "weaponslot pistol" }, new[] { "4", "weaponslot grenade" },
            new[] { "5", "weaponslot smokegrenade" }, new[] { "6", "weaponslot satchel" }, new[] { "7", "weaponslot binocular" },
            new[] { "T", "messagemode" }, new[] { "V", "mp_QuickMessage" }, new[] { "Y", "messagemode2" }, new[] { "G", "mp_quickmap" },
            new[] { "TAB", "+scores" }, new[] { "F1", "vote yes" }, new[] { "F2", "vote no" }, new[] { "F12", "screenshotJPEG" },
        };

        static readonly Color Bg = Color.FromArgb(24, 26, 32);
        static readonly Color Panel = Color.FromArgb(34, 37, 46);
        static readonly Color Accent = Color.FromArgb(91, 99, 241);
        static readonly Color Fg = Color.FromArgb(230, 230, 235);
        static readonly Color Muted = Color.FromArgb(150, 155, 170);

        GameConfig gc;
        Dictionary<string, Button[]> rows = new Dictionary<string, Button[]>();
        Button capturing; string capCmd; int capSlot;
        Label hint;

        public KeyBindForm(string cfgFile)
        {
            gc = GameConfig.Load(cfgFile);
            Text = "Teclas - " + Brand.Name;
            ClientSize = new Size(560, 640);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Bg; ForeColor = Fg; Font = new Font("Segoe UI", 9.5f);

            hint = new Label { Text = "Clic en una tecla y presiona la nueva (teclado, mouse o rueda).  Clic derecho = borrar.  ESC = cancelar.", ForeColor = Muted, Location = new Point(16, 10), Size = new Size(530, 36) };
            var panel = new Panel { Location = new Point(12, 48), Size = new Size(536, 528), AutoScroll = true, BackColor = Bg };

            int y = 4;
            foreach (var a in Actions)
            {
                if (a[0].StartsWith("#"))
                {
                    panel.Controls.Add(new Label { Text = a[0].Substring(1).ToUpper(), Font = new Font("Segoe UI", 9.5f, FontStyle.Bold), ForeColor = Accent, Location = new Point(4, y + 6), AutoSize = true });
                    y += 32;
                    continue;
                }
                string cmd = a[0];
                panel.Controls.Add(new Label { Text = a[1], Location = new Point(8, y + 6), Size = new Size(240, 22) });
                var bs = new Button[2];
                for (int s = 0; s < 2; s++)
                {
                    var b = new RoundButton { Location = new Point(256 + s * 132, y), Size = new Size(124, 30), FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg, Cursor = Cursors.Hand, TabStop = false };
                    b.FlatAppearance.BorderColor = Color.FromArgb(60, 64, 78);
                    int slot = s;
                    b.MouseUp += (o, e) =>
                    {
                        if (capturing != null) return;
                        if (e.Button == MouseButtons.Right) { ClearSlot(cmd, slot); return; }
                        if (e.Button == MouseButtons.Left) StartCapture(b, cmd, slot);
                    };
                    bs[s] = b;
                    panel.Controls.Add(b);
                }
                rows[cmd] = bs;
                y += 34;
            }

            var save = MakeButton("Guardar", 440, true);
            var cancel = MakeButton("Cancelar", 332, false);
            var defs = MakeButton("Teclas originales", 16, false);
            defs.Width = 150;
            save.Click += delegate
            {
                try { gc.Save(); DialogResult = DialogResult.OK; Close(); }
                catch (Exception ex) { MessageBox.Show(this, "No se pudo guardar:\n" + ex.Message); }
            };
            cancel.Click += delegate { Close(); };
            defs.Click += delegate
            {
                if (MessageBox.Show(this, "Volver todas las acciones de esta lista a las teclas originales del juego?", "Teclas", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
                foreach (var a in Actions) if (!a[0].StartsWith("#")) foreach (var k in gc.KeysFor(a[0])) gc.RemoveBind(k);
                foreach (var d in Defaults) gc.SetBind(d[0], d[1]);
                Refresh2();
            };

            Controls.AddRange(new Control[] { hint, panel, save, cancel, defs });
            Refresh2();
            Application.AddMessageFilter(this);
            FormClosed += delegate { Application.RemoveMessageFilter(this); };
            Ui.Modernize(this, 32, Bg, Color.FromArgb(17, 18, 23), Fg, Color.FromArgb(150, 155, 170), Text, false);
        }

        Button MakeButton(string text, int x, bool primary)
        {
            var b = new RoundButton { Text = text, Location = new Point(x, 590), Size = new Size(104, 36), FlatStyle = FlatStyle.Flat, BackColor = primary ? Accent : Panel, ForeColor = Color.White };
            b.FlatAppearance.BorderSize = 0;
            return b;
        }

        void Refresh2()
        {
            foreach (var kv in rows)
            {
                var keys = gc.KeysFor(kv.Key);
                for (int s = 0; s < 2; s++)
                {
                    kv.Value[s].Text = s < keys.Count ? keys[s] : "-";
                    kv.Value[s].BackColor = Panel;
                }
            }
        }

        void ClearSlot(string cmd, int slot)
        {
            var keys = gc.KeysFor(cmd);
            if (slot < keys.Count) gc.RemoveBind(keys[slot]);
            Refresh2();
        }

        void StartCapture(Button b, string cmd, int slot)
        {
            capturing = b; capCmd = cmd; capSlot = slot;
            b.Text = "Presiona...";
            b.BackColor = Accent;
        }

        void Finish(string key)
        {
            var b = capturing; capturing = null;
            if (key != null)
            {
                if (key == "ESCAPE" || key == "`" || key == "~")
                {
                    MessageBox.Show(this, "Esa tecla esta reservada por el juego (menu / consola).");
                }
                else
                {
                    var keys = gc.KeysFor(capCmd);
                    if (capSlot < keys.Count) gc.RemoveBind(keys[capSlot]);   // reemplaza la tecla anterior de ese casillero
                    string prev;
                    if (gc.Binds.TryGetValue(key, out prev) && !string.Equals(prev, capCmd, StringComparison.OrdinalIgnoreCase))
                        hint.Text = "La tecla " + key + " estaba asignada a \"" + prev + "\" y se quito de ahi.";
                    gc.RemoveBind(key);
                    gc.SetBind(key, capCmd);
                }
            }
            Refresh2();
        }

        // ---- Captura global de teclado/mouse mientras se espera una tecla ----
        const int WM_KEYDOWN = 0x100, WM_SYSKEYDOWN = 0x104, WM_LBUTTONDOWN = 0x201, WM_RBUTTONDOWN = 0x204,
                  WM_MBUTTONDOWN = 0x207, WM_MOUSEWHEEL = 0x20A, WM_XBUTTONDOWN = 0x20B,
                  WM_LBUTTONUP = 0x202, WM_RBUTTONUP = 0x205, WM_MBUTTONUP = 0x208, WM_XBUTTONUP = 0x20C, WM_KEYUP = 0x101, WM_SYSKEYUP = 0x105;
        bool swallowUps;

        public bool PreFilterMessage(ref Message m)
        {
            if (capturing == null)
            {
                if (swallowUps && (m.Msg == WM_LBUTTONUP || m.Msg == WM_RBUTTONUP || m.Msg == WM_MBUTTONUP || m.Msg == WM_XBUTTONUP || m.Msg == WM_KEYUP || m.Msg == WM_SYSKEYUP))
                { swallowUps = false; return true; }
                return false;
            }
            string key = null;
            switch (m.Msg)
            {
                case WM_KEYDOWN:
                case WM_SYSKEYDOWN:
                    int vk = m.WParam.ToInt32() & 0xFF;
                    if (vk == 0x1B) { swallowUps = true; Finish(null); return true; }
                    key = VkToCod(vk);
                    if (key == null) { hint.Text = "Esa tecla no se puede usar en el juego. Proba otra."; return true; }
                    break;
                case WM_LBUTTONDOWN: key = "MOUSE1"; break;
                case WM_RBUTTONDOWN: key = "MOUSE2"; break;
                case WM_MBUTTONDOWN: key = "MOUSE3"; break;
                case WM_XBUTTONDOWN: key = ((m.WParam.ToInt64() >> 16) & 0xFFFF) == 1 ? "MOUSE4" : "MOUSE5"; break;
                case WM_MOUSEWHEEL: key = ((short)((m.WParam.ToInt64() >> 16) & 0xFFFF)) > 0 ? "MWHEELUP" : "MWHEELDOWN"; break;
                default: return false;
            }
            swallowUps = m.Msg != WM_MOUSEWHEEL;
            Finish(key);
            return true;
        }

        [DllImport("user32.dll")] static extern uint MapVirtualKey(uint uCode, uint uMapType);

        static string VkToCod(int vk)
        {
            if (vk >= 0x41 && vk <= 0x5A) return ((char)vk).ToString();          // A-Z
            if (vk >= 0x30 && vk <= 0x39) return ((char)vk).ToString();          // 0-9
            if (vk >= 0x70 && vk <= 0x7B) return "F" + (vk - 0x6F);              // F1-F12
            switch (vk)
            {
                case 0x08: return "BACKSPACE";
                case 0x09: return "TAB";
                case 0x0D: return "ENTER";
                case 0x10: return "SHIFT";
                case 0x11: return "CTRL";
                case 0x12: return "ALT";
                case 0x13: return "PAUSE";
                case 0x14: return "CAPSLOCK";
                case 0x20: return "SPACE";
                case 0x21: return "PGUP";
                case 0x22: return "PGDN";
                case 0x23: return "END";
                case 0x24: return "HOME";
                case 0x25: return "LEFTARROW";
                case 0x26: return "UPARROW";
                case 0x27: return "RIGHTARROW";
                case 0x28: return "DOWNARROW";
                case 0x2D: return "INS";
                case 0x2E: return "DEL";
                case 0x60: return "KP_INS";
                case 0x61: return "KP_END";
                case 0x62: return "KP_DOWNARROW";
                case 0x63: return "KP_PGDN";
                case 0x64: return "KP_LEFTARROW";
                case 0x65: return "KP_5";
                case 0x66: return "KP_RIGHTARROW";
                case 0x67: return "KP_HOME";
                case 0x68: return "KP_UPARROW";
                case 0x69: return "KP_PGUP";
                case 0x6A: return "*";
                case 0x6B: return "KP_PLUS";
                case 0x6D: return "KP_MINUS";
                case 0x6E: return "KP_DEL";
                case 0x6F: return "KP_SLASH";
            }
            // Teclas de simbolos (dependen del teclado): usar el caracter si es ASCII
            uint ch = MapVirtualKey((uint)vk, 2) & 0x7FFF;
            if (ch == ';') return "SEMICOLON";
            if (ch > 32 && ch < 127 && ch != '"') return ((char)ch).ToString().ToLowerInvariant();
            return null;
        }
    }
}
