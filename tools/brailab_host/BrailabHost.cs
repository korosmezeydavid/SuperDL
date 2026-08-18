// BraiLab beszédszintetizátor-HOST a SuperDL-hez.
//
// MIÉRT KELL EZ? A BraiLab `TTS.dll` 32 BITES, a SuperDL viszont 64 bites –
// 64 bites folyamatba nem lehet 32 bites DLL-t betölteni. Ezért a DLL egy külön,
// 32 bites kis folyamatban él, és a SuperDL a STANDARD BEMENETÉN küld neki
// parancsokat. (A kapott NVDA-host TCP-portot nyitott; a csővezeték jobb:
// nincs port-ütközés, nincs tűzfal-kérdés, és több példány sem akad össze.)
//
// A DLL API-ját visszafejtéssel és élő mérésekkel állapítottuk meg:
//   TTS_Init(1500, 0)        – stdcall; a kapott NVDA-host is pontosan így hívja
//   TTS_StartSay(wchar_t*)   – a szöveg UTF-16! (a gyári host is
//                              MultiByteToWideChar-ral fordítja oda; ANSI-val
//                              a motor a memóriát olvassa túl és értelmetlen,
//                              hosszú hablatyot mond – élőben megmérve)
//   TTS_Stop()
//   TTS_SetPitch(-1..1)      – CSAK három fokozat, alap 0     (hibakód: -22)
//   TTS_SetTempo(0..5)       – hat fokozat, alap 4            (hibakód: -21)
//   TTS_SetVolume(-1..1)     – három fokozat, alap 0          (hibakód: -23)
//
// Fordítás (a Windows saját C#-fordítójával, nem kell külön eszköz):
//   csc /platform:x86 /target:exe /out:brailab_host.exe BrailabHost.cs
//
// A hangot Ujfalusi Zoltán bocsátotta a rendelkezésünkre – hálás köszönettel.

using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

static class BrailabHost
{
    const string DLL = "TTS.dll";

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_Init(int sampleRate, int mode);

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall,
               CharSet = CharSet.Unicode)]
    static extern int TTS_StartSay([MarshalAs(UnmanagedType.LPWStr)] string text);

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall,
               CharSet = CharSet.Unicode)]
    static extern int TTS_StartSayWithNoIntonation(
        [MarshalAs(UnmanagedType.LPWStr)] string text);

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_Stop();

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_SetPitch(int v);

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_SetTempo(int v);

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_SetVolume(int v);

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_GetPitch();

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_GetTempo();

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_GetVolume();

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_ResetPitch();

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_ResetTempo();

    [DllImport(DLL, CallingConvention = CallingConvention.StdCall)]
    static extern int TTS_ResetVolume();

    static int Szam(string s, int alap)
    {
        int v;
        return int.TryParse(s.Trim(), out v) ? v : alap;
    }

    static int Main(string[] argv)
    {
        // A DLL a saját mappájából olvassa az adatfájlokat, ezért oda állunk.
        try
        {
            string sajat = Path.GetDirectoryName(
                System.Reflection.Assembly.GetExecutingAssembly().Location);
            if (!string.IsNullOrEmpty(sajat))
                Directory.SetCurrentDirectory(sajat);
        }
        catch (Exception) { }

        // Az első paraméter a gyári hostban fixen 1500 (visszafejtve).
        int mintavetel = argv.Length > 0 ? Szam(argv[0], 1500) : 1500;
        int r;
        try
        {
            r = TTS_Init(mintavetel, 0);
        }
        catch (Exception e)
        {
            Console.WriteLine("ERR betoltes " + e.Message.Replace('\n', ' '));
            Console.Out.Flush();
            return 2;
        }
        if (r != 0)
        {
            Console.WriteLine("ERR init " + r);
            Console.Out.Flush();
            return 3;
        }
        Console.WriteLine("READY");         // a hívó ebből tudja, hogy megy
        Console.Out.Flush();

        // A bemenet UTF-8 (a hívó így küldi); a DLL-nek a marshaller adja UTF-16-ban.
        Stream be = Console.OpenStandardInput();
        StreamReader olvaso = new StreamReader(be, new UTF8Encoding(false));
        string sor;
        while ((sor = olvaso.ReadLine()) != null)
        {
            if (sor.Length == 0)
                continue;
            int sp = sor.IndexOf(' ');
            string parancs = (sp < 0 ? sor : sor.Substring(0, sp)).ToUpperInvariant();
            string ertek = sp < 0 ? "" : sor.Substring(sp + 1);
            int v = 0;
            try
            {
                switch (parancs)
                {
                    case "SPEAK":
                        v = TTS_StartSay(ertek);
                        break;
                    case "SPEAKFLAT":            // intonáció nélkül (retró érzet)
                        v = TTS_StartSayWithNoIntonation(ertek);
                        break;
                    case "STOP":
                        v = TTS_Stop();
                        break;
                    case "PITCH":
                        v = TTS_SetPitch(Szam(ertek, 0));
                        break;
                    case "TEMPO":
                        v = TTS_SetTempo(Szam(ertek, 4));
                        break;
                    case "VOLUME":
                        v = TTS_SetVolume(Szam(ertek, 0));
                        break;
                    case "RESET":
                        TTS_ResetPitch();
                        TTS_ResetTempo();
                        TTS_ResetVolume();
                        break;
                    case "GET":
                        Console.WriteLine("VALUES {0} {1} {2}", TTS_GetPitch(),
                                          TTS_GetTempo(), TTS_GetVolume());
                        Console.Out.Flush();
                        continue;
                    case "QUIT":
                        try { TTS_Stop(); } catch (Exception) { }
                        return 0;
                    default:
                        Console.WriteLine("ERR ismeretlen " + parancs);
                        Console.Out.Flush();
                        continue;
                }
            }
            catch (Exception e)
            {
                Console.WriteLine("ERR kivetel " + e.Message.Replace('\n', ' '));
                Console.Out.Flush();
                continue;
            }
            // A visszatérési kódot ÁTADJUK: a hívó így tudja, ha egy fokozat
            // kívül van a motor szűk tartományán (pitch -22, tempo -21, volume -23).
            Console.WriteLine(v == 0 ? "OK" : "ERR " + v);
            Console.Out.Flush();
        }
        return 0;
    }
}
